"""Small-branch GitHub transport. Never checks out or downloads research history."""
from __future__ import annotations
import base64
from collections import OrderedDict
import json
import http.client
import ssl
from pathlib import Path, PurePosixPath
import re
import subprocess
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
from .snapshot import canonical, digest, atomic_write

MAX_FILE = 64 * 1024 * 1024


def path_ok(path):
    if not isinstance(path, str) or not path or len(path)>1024 or '\\' in path or ':' in path or path.startswith('/'):
        raise ValueError('Unsafe transport path')
    if any(p in ('', '.', '..', '.git') for p in path.split('/')):
        raise ValueError('Unsafe transport path')
    return path


def fixed_sha(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{40}',value):
        raise ValueError('Fixed Git SHA required')
    return value


class RemoteError(RuntimeError):
    def __init__(self, status, retry_after=0):
        self.status, self.retry_after = status, retry_after
        super().__init__(f'GitHub request failed (HTTP {status}); no local data removed')


class GitHub:
    def __init__(self, repository, branch, cache, *, actor, gh='gh', local_repository=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
            raise ValueError('Invalid GitHub repository')
        if not re.fullmatch(r'[A-Za-z0-9_/-]+',branch): raise ValueError('Invalid transport branch')
        self.repository, self.branch, self.cache, self.gh = repository, branch, Path(cache), gh
        self.cache.mkdir(parents=True,exist_ok=True)
        self.token = subprocess.check_output([gh,'auth','token','--hostname','github.com'],stderr=subprocess.DEVNULL,text=True).strip()
        self.local_repository=Path(local_repository) if local_repository else None
        self.trees = OrderedDict()
        self.tree_lock=threading.Lock()
        self.cooldown_lock=threading.Lock()
        self.cooldown_file=self.cache/'cooldown.json'
        self.cooldown_until=json.loads(self.cooldown_file.read_bytes()).get('until',0) if self.cooldown_file.exists() else 0
        if self.request('GET','/user')['login'].lower() != actor.lower():
            raise ValueError('gh identity does not match configured actor')

    def request(self, method, endpoint, body=None, *, raw=False, limit=MAX_FILE, params=None):
        if time.time()<self.cooldown_until: raise RemoteError(429,self.cooldown_until-time.time())
        if not endpoint.startswith('/') or '..' in endpoint or '?' in endpoint:
            raise ValueError('Invalid GitHub endpoint')
        prefix = '' if endpoint=='/user' else '/repos/'+self.repository
        req=urllib.request.Request('https://api.github.com'+prefix+endpoint+('?' + urllib.parse.urlencode(params) if params else ''),
            data=None if body is None else canonical(body),method=method,
            headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github.raw+json' if raw else 'application/vnd.github+json',
                     'X-GitHub-Api-Version':'2022-11-28','User-Agent':'benchmark-sync/1','Content-Type':'application/json'})
        for attempt in range(3 if method=='GET' else 1):
            if time.time()<self.cooldown_until: raise RemoteError(429,self.cooldown_until-time.time())
            try:
                with urllib.request.urlopen(req,timeout=45) as res:
                    data=res.read(limit+1)
                break
            except urllib.error.HTTPError as e:
                retry=max(float(e.headers.get('Retry-After','0')),0)
                if e.headers.get('X-RateLimit-Remaining')=='0':
                    retry=max(retry,float(e.headers.get('X-RateLimit-Reset','0'))-time.time())
                if e.code in (403,429):
                    retry=max(retry,60)
                    with self.cooldown_lock:
                        self.cooldown_until=max(self.cooldown_until,time.time()+retry)
                        atomic_write(self.cooldown_file,canonical({'until':self.cooldown_until}))
                raise RemoteError(e.code,retry) from None
            except (urllib.error.URLError,ConnectionError,TimeoutError,ssl.SSLEOFError,http.client.IncompleteRead) as error:
                # A transient read disconnect is safe to retry. Never replay an uncertain
                # POST/PATCH, retry HTTP rejection, or weaken certificate verification.
                reason=getattr(error,'reason',error)
                if method!='GET' or attempt==2 or isinstance(reason,(ssl.SSLCertVerificationError,TimeoutError)): raise
                if time.time()<self.cooldown_until: raise RemoteError(429,self.cooldown_until-time.time()) from None
                time.sleep(.25*2**attempt)
        if len(data)>limit: raise ValueError('GitHub response exceeds byte limit')
        return data if raw else json.loads(data)

    def head(self):
        try: return self.request('GET','/git/ref/heads/'+self.branch)['object']['sha']
        except RemoteError as e:
            if e.status==404: return None
            raise

    def tree(self, commit):
        fixed_sha(commit)
        with self.tree_lock:
            if commit in self.trees:
                self.trees.move_to_end(commit)
                return self.trees[commit]
        # Fixed Git commit trees never change. A small LRU keeps active source trees
        # across snapshot/receipt publications without growing for every channel head.
        meta=self.request('GET','/git/commits/'+commit)
        obj=self.request('GET','/git/trees/'+fixed_sha(meta['tree']['sha']),params={'recursive':'1'})
        if obj.get('truncated') or len(obj['tree'])>100000: raise ValueError('Truncated or excessive Git tree')
        entries={item['path']:item for item in obj['tree'] if item['type']=='blob'}
        with self.tree_lock:
            self.trees[commit]=entries
            self.trees.move_to_end(commit)
            while len(self.trees)>16: self.trees.popitem(last=False)
        return entries

    def local_blob(self,sha):
        repo=getattr(self,'local_repository',None)
        if repo is None: return None
        # Reuse only the exact object ID already obtained from the remote fixed tree.
        # Never read working files, fetch branches, or change any repository state.
        try:
            size=int(subprocess.check_output(['git','-C',str(repo),'cat-file','-s',sha],stderr=subprocess.DEVNULL,timeout=15))
            if size>MAX_FILE: return None
            return subprocess.check_output(['git','-C',str(repo),'cat-file','blob',sha],stderr=subprocess.DEVNULL,timeout=15)
        except (subprocess.CalledProcessError,subprocess.TimeoutExpired,OSError,ValueError):
            return None

    def blob(self, sha, size=None):
        fixed_sha(sha)
        if size is not None and size>MAX_FILE: raise ValueError('Git blob too large')
        target=self.cache/sha
        data=target.read_bytes() if target.exists() else self.local_blob(sha)
        if data is None: data=self.request('GET','/git/blobs/'+sha,raw=True)
        import hashlib
        actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if len(data)>MAX_FILE or actual!=sha or (size is not None and len(data)!=size):
            raise ValueError('Git blob bytes/hash mismatch')
        if not target.exists(): atomic_write(target,data)
        return data

    def read(self, commit, path):
        entry=self.tree(commit).get(path_ok(path))
        if entry is None: raise FileNotFoundError(path)
        if entry['mode']!='100644' and entry['mode']!='100755': raise ValueError('Non-regular Git file')
        return self.blob(entry['sha'],entry.get('size'))

    def put_blob(self,data):
        if len(data)>MAX_FILE: raise ValueError('Git upload too large')
        return self.request('POST','/git/blobs',{'content':base64.b64encode(data).decode(),'encoding':'base64'})['sha']

    def update(self, files, *, parents=(), expected=None):
        """CAS non-force update. Unknown-success retry compares bytes and is idempotent."""
        blob_shas={}
        original=None
        for attempt in range(5):
            head=self.head()
            entries=self.tree(head) if head else {}
            for p,want in (expected or {}).items():
                current=self.blob(entries[p]['sha'],entries[p].get('size')) if p in entries else None
                if current!=want: raise RuntimeError('Channel changed before publication; rebuild against latest generation')
            actual={p:entries.get(p,{}).get('sha') for p in files}
            if original is None: original=actual
            elif actual!=original:
                if all(p in entries and self.blob(entries[p]['sha'],entries[p].get('size'))==d for p,d in files.items()): return head
                raise RuntimeError('Same channel changed concurrently; retry from latest generation')
            changes={p:d for p,d in files.items() if p not in entries or self.blob(entries[p]['sha'],entries[p].get('size'))!=d}
            if not changes: return head
            for p,data in changes.items():
                path_ok(p)
                key=digest(data)
                if key not in blob_shas: blob_shas[key]=self.put_blob(data)
            body={'tree':[{'path':p,'mode':'100644','type':'blob','sha':blob_shas[digest(data)]} for p,data in changes.items()]}
            if head: body['base_tree']=self.request('GET','/git/commits/'+head)['tree']['sha']
            tree=self.request('POST','/git/trees',body)['sha']
            ps=([head] if head else [])+[fixed_sha(p) for p in parents if p!=head]
            commit=self.request('POST','/git/commits',{'message':'Automatic benchmark synchronization','tree':tree,'parents':ps})['sha']
            try:
                if head: self.request('PATCH','/git/refs/heads/'+self.branch,{'sha':commit,'force':False})
                else: self.request('POST','/git/refs',{'ref':'refs/heads/'+self.branch,'sha':commit})
                return commit
            except RemoteError as e:
                if e.status not in (409,422): raise
        raise RuntimeError('Concurrent sync updates; retry on next cycle')
