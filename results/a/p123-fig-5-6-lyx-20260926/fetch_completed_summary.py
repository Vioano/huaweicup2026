"""Fetch the pinned c665 summary blob with the existing gh login."""
import argparse, base64, hashlib, json, subprocess
from pathlib import Path
REPO='huaweibei123/huaweicup2026'
COMMIT='1c00079aadbd071de62db17686d5ba3fed1da0f2'
SOURCE_PATH='results/a/q2-nikolastarx/hypergap-full500-audit-20260925/completed-summary.json'
BLOB='0e027252b773c232d4271a0229d5537f3511641f'
SIZE=1058551
SHA256='083c3f5b603cb61dd8b132718b6437b35c7706ff3aa165bdcdd490617547a2f2'
def api(endpoint): return json.loads(subprocess.check_output(['gh','api',endpoint]))
def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    meta=api(f'repos/{REPO}/contents/{SOURCE_PATH}?ref={COMMIT}')
    if meta['sha']!=BLOB or meta['size']!=SIZE: raise ValueError('pinned identity mismatch')
    blob=api(f'repos/{REPO}/git/blobs/{BLOB}')
    if blob.get('encoding')!='base64': raise ValueError('expected base64 blob')
    raw=base64.b64decode(''.join(blob['content'].split()),validate=True)
    git=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    digest=hashlib.sha256(raw).hexdigest()
    if len(raw)!=SIZE or git!=BLOB or digest!=SHA256: raise ValueError('size/hash mismatch')
    doc=json.loads(raw)
    if len(doc['rows'])!=500: raise ValueError('expected 500 rows')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.exists():
        if a.output.read_bytes()!=raw: raise FileExistsError('different output exists')
    else:
        with a.output.open('xb') as f: f.write(raw)
    print(json.dumps({'bytes':len(raw),'blob_sha':git,'sha256':digest,'rows':len(doc['rows'])}))
if __name__=='__main__': main()
