"""Independently verify existing member receipts; no production writes or uploads."""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
if __package__:
    from .audit import canonical, digest, require, verify_envelope, verify_snapshot
else:
    from audit import canonical, digest, require, verify_envelope, verify_snapshot


def check_receipt(envelope, pem, fingerprint, identity, actor):
    require(digest(pem) == fingerprint == envelope['key_sha256'], 'untrusted receipt key')
    require((envelope['schema_version'], envelope['project'], envelope['domain'], envelope['issuer'])
            == (1, 'huaweicup2026-benchmark-board', 'receipt', 'nikolastarx'), 'wrong receipt context')
    key = load_pem_public_key(pem)
    require(isinstance(key, Ed25519PublicKey), 'wrong receipt key type')
    key.verify(base64.b64decode(envelope['signature'], validate=True),
               canonical({k:v for k,v in envelope.items() if k != 'signature'}))
    payload = envelope['payload']
    require(payload['id'] == identity and payload['actor'] == actor
            and payload['state'] in ('accepted', 'rejected'), 'receipt identity/state mismatch')
    return payload


def audit_receipts(state, fingerprint):
    config = json.loads((state/'config.json').read_bytes())
    pem = config['trusted_keys']['nikolastarx'].encode()
    repository, branch = config['repository'], config['branch']
    def api(path):
        return json.loads(subprocess.check_output(['gh','api','repos/'+repository+'/'+path],
            env=dict(os.environ,GODEBUG='http2client=0'), timeout=90))
    head = api('git/ref/heads/'+branch)['object']['sha']
    tree = api('git/trees/'+head+'?recursive=1')
    require(not tree.get('truncated'), 'receipt tree truncated')
    blobs = {e['path']:e for e in tree['tree'] if e['type']=='blob'}
    manifest = json.loads((state/'accepted/current.json').read_bytes())
    require(verify_envelope(manifest['_channel'],pem,fingerprint)
            == {k:v for k,v in manifest.items() if k not in ('_channel','verified_at')}, 'snapshot signature mismatch')
    snapshot = verify_snapshot(manifest,(state/'accepted'/manifest['payload_file']).read_bytes())
    entries = []
    for path in sorted((state/'outbox').glob('*/entry.json')):
        local = json.loads(path.read_bytes())
        payload = local['payload']; identity = digest(canonical(payload)); actor = payload['actor']
        require(local['id']==identity==path.parent.name, 'local submission identity mismatch')
        item = dict(id=identity,actor=actor,commit=payload['commit'],feed=payload['feed'],
                    queued_at=local['queued_at'],state=local['state'],error=local.get('error'))
        remote_path = f'receipts/{actor}/{identity}.json'
        if remote_path in blobs:
            blob = blobs[remote_path]
            raw = base64.b64decode(api('git/blobs/'+blob['sha'])['content'])
            require(len(raw)==blob['size'] and hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blob['sha'], 'receipt Git blob differs')
            envelope=json.loads(raw)
            receipt=check_receipt(envelope,pem,fingerprint,identity,actor)
            item.update(signed_envelope=envelope,remote_git_blob=blob['sha'],signature_verified=True,
                        local_receipt_equal=local.get('receipt')==receipt)
            if local['state'] in ('accepted','rejected'):
                require(item['local_receipt_equal'] and local['state']==receipt['state'], 'local receipt differs from authority')
            item['seconds_queued_to_central_receipt']=(datetime.fromisoformat(receipt['received_at'])-datetime.fromisoformat(local['queued_at'])).total_seconds()
            matching=[r for r in snapshot['records'] if r['source'].get('commit')==payload['commit'] and r['source'].get('path')==payload['feed']]
            item['snapshot_source_records']=[dict(id=r['id'],problem=r['problem'],case_id=r['case_id'],cores=r['cores'],eligible=r['eligible']) for r in matching]
            item['scope']='Signature and local receipt equality; source record linkage is reported separately from admission and scientific verification.'
        else:
            require(local['state'] not in ('accepted','rejected'), 'terminal local state lacks authoritative receipt')
            item['signature_verified']=False
            item['scope']='No receipt at this fixed channel commit; pending is not accepted.'
        entries.append(item)
    return dict(checked_at=datetime.now(timezone.utc).isoformat(),repository=repository,channel_commit=head,
                snapshot_id=snapshot['snapshot_id'],snapshot_records=len(snapshot['records']),entries=entries,
                limitations='Receipt interval spans different machines clocks and excludes unobserved local/display arrival time. New production feeds may continue to arrive.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sync-state',required=True,type=Path)
    p.add_argument('--key-sha256',required=True)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args(); result=audit_receipts(args.sync_state,args.key_sha256)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(channel_commit=result['channel_commit'],snapshot_records=result['snapshot_records'],
                         entries=[{k:e.get(k) for k in ('id','state','signature_verified','local_receipt_equal','seconds_queued_to_central_receipt')} for e in result['entries']])) )
