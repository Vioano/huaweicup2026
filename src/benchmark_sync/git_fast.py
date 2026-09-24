"""Small signed snapshot deltas over a shallow Git branch, with REST as fallback."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import threading
import uuid

from .github import fixed_sha, path_ok

MAX_FAST_FILE = 5 * 1024 * 1024


class FastGitError(RuntimeError):
    pass


class GitFastLane:
    def __init__(self, state, repository, branch='benchmark-fast-v1', *, git='git'):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):
            raise ValueError('Invalid fast Git repository')
        if not re.fullmatch(r'[A-Za-z0-9_/-]+',branch):
            raise ValueError('Invalid fast Git branch')
        self.root=Path(state)/'fast-git'
        self.root.parent.mkdir(parents=True,exist_ok=True)
        self.git=git
        self.branch=branch
        self.ref='refs/heads/'+branch
        self.url='https://github.com/'+repository+'.git'
        self.lock=threading.RLock()
        self.cached_head=None
        if not (self.root/'HEAD').exists():
            self._run(['init','--bare','--quiet',str(self.root)],at_root=False)
        try: current=self._run(['remote','get-url','origin']).decode().strip()
        except FastGitError:
            self._run(['remote','add','origin',self.url]);current=self.url
        if current!=self.url:
            raise ValueError('Fast Git remote does not match the configured repository')

    def _run(self,args,*,data=None,env=None,timeout=20,at_root=True):
        command=[self.git]
        if at_root: command+=['-C',str(self.root)]
        command+=args
        process_env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
        if env: process_env.update(env)
        try:
            result=subprocess.run(command,input=data,stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,env=process_env,timeout=timeout)
        except (OSError,subprocess.TimeoutExpired) as error:
            raise FastGitError('Fast Git command unavailable or timed out: '+args[0]) from error
        if result.returncode:
            raise FastGitError('Fast Git command failed: '+args[0])
        return result.stdout

    def head(self):
        """Return a fetched immutable commit; unchanged checks fetch no objects."""
        with self.lock:
            output=self._run(['ls-remote','origin',self.ref],timeout=10).decode().strip()
            if not output: return None
            fields=output.split()
            if len(fields)!=2 or fields[1]!=self.ref: raise ValueError('Unexpected fast Git ref')
            remote_head=fixed_sha(fields[0])
            if remote_head==self.cached_head: return remote_head
            self._run(['fetch','--no-tags','--depth=1','origin',self.ref],timeout=20)
            fetched=fixed_sha(self._run(['rev-parse','FETCH_HEAD']).decode().strip())
            self.cached_head=fetched
            return fetched

    def read_path(self,commit,path):
        fixed_sha(commit);path_ok(path)
        if path!='channels/fast.json' and not re.fullmatch(r'deltas/[0-9a-f]{64}\.json\.gz',path):
            raise ValueError('Unsupported fast Git path')
        object_name=commit+':'+path
        with self.lock:
            try: size=int(self._run(['cat-file','-s',object_name]).decode())
            except FastGitError as error: raise FileNotFoundError(path) from error
            if size<0 or size>MAX_FAST_FILE: raise ValueError('Fast Git object exceeds byte limit')
            data=self._run(['show',object_name])
            if len(data)!=size: raise ValueError('Fast Git object size mismatch')
            return data

    def update(self,files,*,expected=None):
        """Replace the tiny branch tree with one channel and its immutable delta."""
        delta_paths=[path for path in files if re.fullmatch(r'deltas/[0-9a-f]{64}\.json\.gz',path)]
        if len(files)!=2 or 'channels/fast.json' not in files or len(delta_paths)!=1:
            raise ValueError('Fast Git update must contain one channel and one delta')
        if any(len(data)>MAX_FAST_FILE for data in files.values()):
            raise ValueError('Fast Git update exceeds byte limit')
        with self.lock:
            parent=self.head()
            prior=None
            if parent:
                try: prior=self.read_path(parent,'channels/fast.json')
                except FileNotFoundError: prior=None
            if expected is not None and prior!=expected:
                raise ValueError('Fast Git channel changed before publication')
            if prior==files['channels/fast.json']: return parent
            index=self.root/('index-'+uuid.uuid4().hex)
            env={'GIT_INDEX_FILE':str(index),
                 'GIT_AUTHOR_NAME':'benchmark-sync','GIT_AUTHOR_EMAIL':'benchmark-sync@invalid',
                 'GIT_COMMITTER_NAME':'benchmark-sync','GIT_COMMITTER_EMAIL':'benchmark-sync@invalid'}
            try:
                self._run(['read-tree','--empty'],env=env)
                for path,data in sorted(files.items()):
                    path_ok(path)
                    blob=fixed_sha(self._run(['hash-object','-w','--stdin'],data=data).decode().strip())
                    self._run(['update-index','--add','--cacheinfo',f'100644,{blob},{path}'],env=env)
                tree=fixed_sha(self._run(['write-tree'],env=env).decode().strip())
                args=['commit-tree',tree]
                if parent: args+=['-p',parent]
                commit=fixed_sha(self._run(args,data=b'Automatic signed benchmark delta\n',env=env).decode().strip())
                try: self._run(['push','origin',commit+':'+self.ref],timeout=20)
                except FastGitError:
                    latest=self.head()
                    if latest and self.read_path(latest,'channels/fast.json')==files['channels/fast.json']:
                        return latest
                    raise
                self.cached_head=commit
                return commit
            finally:
                index.unlink(missing_ok=True)
