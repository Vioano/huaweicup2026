"""Discover committed producer feeds, preserve original bytes, enqueue durable requests."""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
from .github import path_ok, fixed_sha, MAX_FILE
from .snapshot import canonical, digest, atomic_write, now, unpack, payload_name

MAX_FEED=8*1024*1024
MAX_VERIFY_BATCH=8*1024*1024


def references(feed):
    if not isinstance(feed,dict): raise ValueError('Benchmark feed must be an object')
    if feed.get('schema_version')!=1 or not isinstance(feed.get('records'),list) or not 0<len(feed['records'])<=5000:
        raise ValueError('Expected nonempty standard benchmark feed (at most 5000 records)')
    refs={}
    def visit(value):
        if isinstance(value,dict):
            if 'path' in value and 'sha256' in value and isinstance(value['path'],str):
                p=path_ok(value['path']); h=value['sha256']
                if not p.startswith(('results/','docs/','data/','tasks/')) or not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h):
                    raise ValueError('Invalid benchmark artifact reference')
                if p in refs and refs[p]!=h: raise ValueError('Conflicting artifact reference')
                refs[p]=h
            else:
                for v in value.values(): visit(v)
        elif isinstance(value,list):
            for v in value: visit(v)
    # Only actual admission artifacts, not arbitrary provenance dictionaries.
    for record in feed['records']:
        if not isinstance(record,dict): raise ValueError('Benchmark record must be an object')
        provenance=record.get('provenance',{})
        if not isinstance(provenance,dict): raise ValueError('Benchmark provenance must be an object')
        if not isinstance(provenance.get('producer_session',''),str): raise ValueError('Benchmark producer_session must be a string')
        visit(record.get('artifacts',{}))
        visit(record.get('baseline'))
        visit(record.get('cache_pair'))
    return refs


def git(repo,*args):
    return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL,timeout=60)


def verify_commit_artifacts(repo,commit,refs):
    """Verify fixed-commit artifacts with bounded tree/blob batches, not one Git process per file."""
    fixed_sha(commit)
    paths=list(refs);chunks=[];chunk=[];arg_bytes=0
    for path in paths:
        size=len(path.encode('utf-8'))+16
        if chunk and (len(chunk)>=128 or arg_bytes+size>12000):
            chunks.append(chunk);chunk=[];arg_bytes=0
        chunk.append(path);arg_bytes+=size
    if chunk: chunks.append(chunk)
    objects={}
    for chunk in chunks:
        raw=git(repo,'--literal-pathspecs','ls-tree','-r','-l','-z','--full-tree',commit,'--',*chunk)
        for item in raw.split(b'\0'):
            if not item: continue
            metadata,separator,name=item.partition(b'\t')
            if not separator: raise ValueError('Malformed fixed-commit tree entry')
            fields=metadata.decode('ascii').split()
            if len(fields)!=4: raise ValueError('Malformed fixed-commit tree metadata')
            mode,kind,oid,size=fields
            path=name.decode('utf-8')
            if path in refs:
                try: size=int(size)
                except ValueError: raise ValueError('Artifact size missing from fixed commit: '+path) from None
                if kind!='blob' or mode not in ('100644','100755') or size<0 or size>MAX_FILE:
                    raise ValueError('Artifact is not a bounded regular file: '+path)
                objects[path]=(fixed_sha(oid),size)
    missing=set(paths)-objects.keys()
    if missing: raise ValueError('Missing artifact in fixed commit: '+sorted(missing)[0])
    unique={oid:size for oid,size in objects.values()}
    ordered=[];batch=[];batch_size=0
    for oid,size in unique.items():
        if batch and batch_size+size>MAX_VERIFY_BATCH:
            ordered.append(batch);batch=[];batch_size=0
        batch.append((oid,size));batch_size+=size
    if batch: ordered.append(batch)
    verified={}
    for batch in ordered:
        request=''.join(oid+'\n' for oid,_ in batch).encode('ascii')
        result=subprocess.run(['git','-C',str(repo),'cat-file','--batch'],input=request,
                              stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=60,check=True)
        raw=result.stdout;offset=0
        for expected_oid,expected_size in batch:
            end=raw.find(b'\n',offset)
            if end<0: raise ValueError('Truncated batched Git object header')
            fields=raw[offset:end].decode('ascii').split()
            if len(fields)!=3 or fields[0]!=expected_oid or fields[1]!='blob':
                raise ValueError('Unexpected object in batched Git artifact read')
            try: size=int(fields[2])
            except ValueError: raise ValueError('Invalid batched Git object size') from None
            if size!=expected_size: raise ValueError('Fixed-commit artifact size mismatch')
            start=end+1;finish=start+size
            if finish>=len(raw) or raw[finish:finish+1]!=b'\n': raise ValueError('Truncated batched Git object bytes')
            verified[expected_oid]=digest(raw[start:finish]);offset=finish+1
        if offset!=len(raw): raise ValueError('Extra bytes in batched Git artifact response')
    for path,expected in refs.items():
        oid,_=objects[path]
        if verified.get(oid)!=expected: raise ValueError('Local artifact bytes/hash mismatch: '+path)


def enqueue(state, repo, commit, feed_path, actor):
    fixed_sha(commit); path_ok(feed_path)
    data=git(repo,'show',commit+':'+feed_path)
    if len(data)>MAX_FEED: raise ValueError('Feed exceeds 8 MiB')
    feed=json.loads(data); refs=references(feed)
    producers={r.get('provenance',{}).get('producer_session','').split('/')[0].lower() for r in feed['records']}
    if producers!={actor}: raise ValueError('Feed producer_session must match authenticated uploader')
    # Verify complete bytes before announcing; transport errors cannot become reported scores.
    verify_commit_artifacts(repo,commit,refs)
    payload={'schema_version':1,'actor':actor,'commit':commit,'feed':feed_path,
             'feed_sha256':digest(data),'artifacts':refs}
    identity=digest(canonical(payload))
    entry=Path(state)/'outbox'/identity/'entry.json'
    if not entry.exists():
        atomic_write(entry,canonical({'id':identity,'payload':payload,'repo':str(Path(repo).resolve()),
                                     'state':'queued','queued_at':now(),'error':None}))
    return identity


def parse_worktree_heads(output):
    """Parse Git's NUL-delimited porcelain records, including each embedded HEAD."""
    found=[];current=None
    for item in output.split('\0'):
        if item.startswith('worktree '):
            if current and current[1]: found.append(tuple(current))
            current=[item[9:],None]
        elif item.startswith('HEAD ') and current:
            current[1]=item[5:]
    if current and current[1]: found.append(tuple(current))
    return found


def discover(state, roots, actor, *, known_record_ids=None):
    """Watch registered worktrees; accepted IDs prevent re-uploading historical batches."""
    state=Path(state); cursor_file=state/'watch-cursors.json'
    cursors=json.loads(cursor_file.read_bytes()) if cursor_file.exists() else {}
    errors=[]; known=set(known_record_ids or ()); accepted=state/'accepted'/'current.json'
    if known_record_ids is None and accepted.exists():
        manifest=json.loads(accepted.read_bytes())
        payload=unpack((accepted.parent/payload_name(manifest)).read_bytes(),manifest)
        known={r['id'] for r in payload['records']}
    for root in roots:
        try:
            output=git(root,'worktree','list','--porcelain','-z').decode('utf-8')
            worktrees=parse_worktree_heads(output)
        except Exception as error:
            errors.append({'repository':str(root),'error':str(error)}); continue
        for repo,commit in worktrees:
            try:
                previous=cursors.get(repo)
                if previous==commit: continue
                # A cursor means every feed at that tree was handled. Reading all
                # historical feed blobs again on each HEAD change delays new work
                # as the repository grows; inspect only additions/modifications.
                # A missing/pruned cursor falls back to the complete first scan.
                if previous:
                    try:
                        names=git(repo,'diff','--no-ext-diff','--no-renames',
                                  '--diff-filter=ACMRT','--name-only','-z',previous,commit,
                                  '--','results').decode('utf-8').split('\0')
                    except subprocess.CalledProcessError:
                        names=git(repo,'ls-tree','-r','--name-only','-z',commit,'--','results').decode('utf-8').split('\0')
                else:
                    names=git(repo,'ls-tree','-r','--name-only','-z',commit,'--','results').decode('utf-8').split('\0')
                failed=False
                for name in names:
                    if not (Path(name).name.startswith('board-feed') and name.endswith('.json')): continue
                    try:
                        raw=git(repo,'show',commit+':'+name)
                        if len(raw)>MAX_FEED: raise ValueError('Feed exceeds byte limit')
                        feed=json.loads(raw)
                        producers={r.get('provenance',{}).get('producer_session','').split('/')[0].lower() for r in feed.get('records',[])}
                        if producers!={actor}: continue
                        if all(digest(canonical(r)) in known for r in feed['records']): continue
                        origin=git(repo,'log','-1','--format=%H',commit,'--',name).decode().strip()
                        enqueue(state,repo,origin,name,actor)
                    except Exception as error:
                        errors.append({'repository':repo,'feed':name,'error':str(error)});failed=True
                if not failed:
                    cursors[repo]=commit
                    atomic_write(cursor_file,canonical(cursors))
            except Exception as error: errors.append({'repository':repo,'error':str(error)})
    return errors
