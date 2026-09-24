"""Discover committed producer feeds, preserve original bytes, enqueue durable requests."""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
from .github import path_ok, fixed_sha, MAX_FILE
from .snapshot import canonical, digest, atomic_write, now, unpack, payload_name

MAX_FEED=8*1024*1024


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


def enqueue(state, repo, commit, feed_path, actor):
    fixed_sha(commit); path_ok(feed_path)
    data=git(repo,'show',commit+':'+feed_path)
    if len(data)>MAX_FEED: raise ValueError('Feed exceeds 8 MiB')
    feed=json.loads(data); refs=references(feed)
    producers={r.get('provenance',{}).get('producer_session','').split('/')[0].lower() for r in feed['records']}
    if producers!={actor}: raise ValueError('Feed producer_session must match authenticated uploader')
    # Verify complete bytes before announcing; transport errors cannot become reported scores.
    for path,sha in refs.items():
        value=git(repo,'show',commit+':'+path)
        if len(value)>MAX_FILE or digest(value)!=sha: raise ValueError('Local artifact bytes/hash mismatch: '+path)
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
                if cursors.get(repo)==commit: continue
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
