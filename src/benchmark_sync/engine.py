"""Non-LLM durable bidirectional synchronization. The board remains the sole ledger writer."""
from __future__ import annotations
import gzip
import json
import re
from pathlib import Path
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime
from .github import fixed_sha, path_ok, RemoteError, MAX_FILE
from .snapshot import (atomic_write, canonical, digest, now, read_central, publish_files,
                       unpack, reject_history_regression, payload_name, git_json)
from .submission import discover, references, MAX_FEED
from .delta import pack_delta, unpack_delta
from .git_fast import GitFastLane

OUTBOX_PUBLISH_BATCH_SIZE = 16
OUTBOX_RECEIPT_CHECK_BATCH_SIZE = 16
SNAPSHOT_SEMANTIC_FIELDS = ('schema_version','generated_at','sequence','snapshot_id',
                            'record_count','record_ids_sha256','records_sha256','publisher','payload_file','decoded_size')


def same_snapshot_semantics(left,right):
    return all(left.get(key)==right.get(key) for key in SNAPSHOT_SEMANTIC_FIELDS)


def submission_lane(actor):
    if not isinstance(actor,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,39}',actor):
        raise ValueError('Invalid submission actor')
    return 'benchmark-submissions/'+actor.lower()


def read_json(path): return json.loads(Path(path).read_bytes())
def write_json(path,value): atomic_write(Path(path),canonical(value)+b'\n')


class Engine:
    def __init__(self,config,remote,signatures):
        self.config=config; self.remote=remote; self.signatures=signatures
        self.state=Path(config['state']); self.state.mkdir(parents=True,exist_ok=True)
        self.actor=config['actor']; self.leader=config['leader']; self.role=config['role']
        self.trusted=config['trusted_keys']; self.key=Path(config['private_key'])
        self.errors=[]
        self._submission_locks={}
        self._submission_locks_guard=threading.Lock()
        self.receive_status={}
        self._accepted_cache_key=None
        self._accepted_payload_cache=None
        self._upload_thread=None
        self._upload_status={'stage':'idle','started_at':None,'finished_at':None,'errors':[]}
        self._receive_thread=None
        self._receive_worker_status={'stage':'idle','started_at':None,'finished_at':None,'pending':0,'errors':[]}
        self._local_fastpath_status={'state':'idle','delivery_id':None,'started_at':None,
                                     'finished_at':None,'error':None}
        self._git_fast_lane=None
        self._publish_thread=None
        self._publish_worker_status={'state':'idle','started_at':None,'finished_at':None,
                                     'sequence':None,'snapshot_id':None,'payload_sha256':None,
                                     'error':None}

    def sign(self,domain,payload): return self.signatures.sign(domain,self.actor,payload,self.key)
    def submission_lock(self,identity):
        with self._submission_locks_guard:
            return self._submission_locks.setdefault(identity,threading.RLock())
    def verify(self,envelope,domain,*,central=False):
        keys={self.leader:self.trusted[self.leader]} if central else self.trusted
        return self.signatures.verify(envelope,domain=domain,trusted_keys=keys)

    def channel(self,head,name,domain,*,remote=None):
        source=remote or self.remote
        try: envelope=json.loads(source.read_path(head,'channels/'+name+'.json'))
        except FileNotFoundError: return None,None
        payload=self.verify(envelope,domain,central=True)
        if type(payload.get('generation')) is not int or payload['generation']<1: raise ValueError('Invalid channel generation')
        return payload,envelope

    def accepted_payload(self,manifest):
        path=self.state/'accepted'/payload_name(manifest)
        data=path.read_bytes()
        # The signed compressed hash is checked on every cycle. Once this exact
        # immutable snapshot has been fully unpacked and validated in this process,
        # retain its parsed value instead of repeatedly inflating and JSON-decoding it.
        if len(data)!=manifest.get('payload_size') or digest(data)!=manifest.get('payload_sha256'):
            raise ValueError('Snapshot compressed bytes/hash mismatch')
        key=(manifest.get('payload_sha256'),manifest.get('payload_size'),manifest.get('snapshot_id'))
        if self._accepted_cache_key==key and self._accepted_payload_cache is not None:
            return self._accepted_payload_cache
        payload=unpack(data,manifest)
        if '_fast_channel' in manifest:
            fast=self.verify(manifest['_fast_channel'],'snapshot-delta',central=True)
            if digest(canonical(payload))!=fast.get('target_canonical_sha256'):
                raise ValueError('Accepted fast snapshot differs from signed canonical content')
        self._accepted_cache_key=key;self._accepted_payload_cache=payload
        return payload

    def accepted_record_ids(self):
        current=self.state/'accepted'/'current.json'
        if not current.exists(): return None
        payload=self.accepted_payload(read_json(current))
        return {record['id'] for record in payload['records']}

    def accept_snapshot(self,head):
        channel,envelope=self.channel(head,'central','snapshot')
        if channel is None: return
        output=self.state/'accepted'; current=output/'current.json'
        previous=read_json(current) if current.exists() else None
        if previous and '_fast_channel' in previous:
            fast=self.verify(previous['_fast_channel'],'snapshot-delta',central=True)
            if (set(previous)!=(set(fast['target_manifest'])|{'_fast_channel','verified_at'}) or
                    not same_snapshot_semantics(previous,fast['target_manifest'])):
                raise ValueError('Accepted fast snapshot metadata does not match its signed channel')
            manifest=channel['manifest']
            if channel['generation']<fast['base_generation']:
                raise ValueError('Full snapshot generation rollback behind fast base')
            if channel['generation']==fast['base_generation'] and manifest!=fast['base_manifest']:
                raise ValueError('Full snapshot base generation reused for different content')
            if channel['generation']==fast['base_generation'] or manifest['sequence']<previous['sequence']:
                self.accepted_payload(previous)
                return
            if manifest['sequence']==previous['sequence'] and manifest['records_sha256']!=previous['records_sha256']:
                raise ValueError('Full snapshot rewrote fast accepted records')
            if same_snapshot_semantics(manifest,previous):
                self.accepted_payload(previous)
                if manifest=={k:v for k,v in previous.items() if k not in ('_fast_channel','verified_at')}:
                    write_json(current,dict(manifest,_channel=envelope,verified_at=now()))
                return
        if previous and '_channel' in previous:
            prior=self.verify(previous['_channel'],'snapshot',central=True)
            if previous!=dict(prior['manifest'],_channel=previous['_channel'],verified_at=previous.get('verified_at')):
                raise ValueError('Accepted snapshot metadata does not match its signed channel')
            if channel['generation']<prior['generation']: raise ValueError('Signed snapshot generation rollback')
            if channel['generation']==prior['generation']:
                if channel!=prior: raise ValueError('Snapshot generation reused for different content')
                # The signed compressed hash/size is still checked every cycle;
                # decompression and full semantic validation happen once per process.
                self.accepted_payload(prior['manifest'])
                return
        manifest=channel['manifest']; path=path_ok(channel['object'])
        if path!='objects/'+manifest['payload_sha256']: raise ValueError('Snapshot object identity mismatch')
        data=self.remote.read_path(head,path); payload=unpack(data,manifest)
        if payload['publisher']['actor']!=self.leader: raise ValueError('Wrong snapshot authority')
        if previous:
            if '_channel' in previous:
                prior=self.verify(previous['_channel'],'snapshot',central=True)
                reject_history_regression(self.accepted_payload(prior['manifest']),payload)
            else:
                reject_history_regression(unpack((output/payload_name(previous)).read_bytes(),previous),payload)
        atomic_write(output/payload_name(manifest),data)
        write_json(current,dict(manifest,_channel=envelope,verified_at=now()))
        self._accepted_cache_key=(manifest.get('payload_sha256'),manifest.get('payload_size'),manifest.get('snapshot_id'))
        self._accepted_payload_cache=payload

    def accept_fast_snapshot(self,head,*,remote=None,base_head=None):
        """Install a signed small change while the full object is still uploading."""
        source=remote or self.remote
        fast,envelope=self.channel(head,'fast','snapshot-delta',remote=source)
        if fast is None: return
        if (source is self.remote and fast.get('transport','rest')!='rest') or (source is not self.remote and fast.get('transport')!='git'):
            raise ValueError('Fast snapshot transport mismatch')
        if fast.get('schema_version')!=1 or type(fast.get('base_generation')) is not int or fast['base_generation']<1:
            raise ValueError('Invalid fast snapshot channel')
        base_manifest=fast.get('base_manifest');target_manifest=fast.get('target_manifest')
        if not isinstance(base_manifest,dict) or not isinstance(target_manifest,dict):
            raise ValueError('Fast snapshot manifests missing')
        base_object=path_ok(fast.get('base_object'));delta_object=path_ok(fast.get('delta_object'))
        if base_object!='objects/'+base_manifest.get('payload_sha256','') or delta_object!='deltas/'+fast.get('delta_sha256','')+'.json.gz':
            raise ValueError('Fast snapshot object identity mismatch')
        if type(fast.get('delta_size')) is not int or fast['delta_size']<1:
            raise ValueError('Fast snapshot delta size invalid')
        output=self.state/'accepted';current=output/'current.json'
        previous=read_json(current) if current.exists() else None
        if previous and '_fast_channel' in previous:
            prior=self.verify(previous['_fast_channel'],'snapshot-delta',central=True)
            if (fast.get('transport','rest')==prior.get('transport','rest') and
                    (fast['generation']<prior['generation'] or
                     (fast['generation']==prior['generation'] and fast!=prior))):
                raise ValueError('Fast snapshot generation rollback')
        if previous:
            if previous['sequence']>target_manifest['sequence']:
                self.accepted_payload(previous);return
            if (previous['sequence']==target_manifest['sequence'] and
                    previous['records_sha256']!=target_manifest['records_sha256']):
                raise ValueError('Fast snapshot rewrote accepted records')
            if (previous['sequence']==target_manifest['sequence'] and
                    target_manifest['generated_at']<=previous['generated_at']):
                self.accepted_payload(previous);return
            if '_channel' in previous:
                full=self.verify(previous['_channel'],'snapshot',central=True)
                if full['generation']>fast['base_generation'] and previous['sequence']>=target_manifest['sequence']:
                    self.accepted_payload(previous);return
            if previous['snapshot_id']==target_manifest['snapshot_id']:
                self.accepted_payload(previous);return
        base_path=output/payload_name(base_manifest)
        if previous and previous['snapshot_id']==base_manifest.get('snapshot_id'):
            base=self.accepted_payload(previous)
        elif base_path.exists():
            try: base=unpack(base_path.read_bytes(),base_manifest)
            except ValueError:
                if source is not self.remote and base_head is None:
                    raise FileNotFoundError('REST base snapshot is not cached yet')
                data=self.remote.read_path(base_head or head,base_object)
                base=unpack(data,base_manifest)
                atomic_write(base_path,data)
        else:
            if source is not self.remote and base_head is None:
                raise FileNotFoundError('REST base snapshot is not cached yet')
            data=self.remote.read_path(base_head or head,base_object)
            base=unpack(data,base_manifest)
            atomic_write(base_path,data)
        delta=source.read_path(head,delta_object)
        if len(delta)!=fast['delta_size'] or digest(delta)!=fast['delta_sha256']:
            raise ValueError('Fast snapshot delta bytes/hash mismatch')
        target=unpack_delta(base,delta)
        raw=canonical(target)
        if digest(raw)!=fast.get('target_canonical_sha256'):
            raise ValueError('Fast snapshot canonical content mismatch')
        compressed=gzip.compress(raw,mtime=0)
        if target['snapshot_id']!=target_manifest.get('snapshot_id'):
            raise ValueError('Fast snapshot target identity mismatch')
        local_manifest=dict(target_manifest,payload_sha256=digest(compressed),payload_size=len(compressed))
        if unpack(compressed,local_manifest)!=target:
            raise ValueError('Fast snapshot reconstruction mismatch')
        if previous: reject_history_regression(self.accepted_payload(previous),target)
        atomic_write(output/payload_name(local_manifest),compressed)
        write_json(current,dict(local_manifest,_fast_channel=envelope,verified_at=now()))
        self._accepted_cache_key=(local_manifest['payload_sha256'],local_manifest['payload_size'],local_manifest['snapshot_id'])
        self._accepted_payload_cache=target

    def _finish_snapshot_publication(self,head,previous,envelope,manifest,data,payload_bytes,target_sha):
        if previous and data is not None:
            self.publish_fast_delta(head,previous,None,None,manifest,data=data,
                                    target_canonical_sha256=target_sha)
        path='objects/'+manifest['payload_sha256']
        channel={'generation':(previous['generation']+1 if previous else 1),'manifest':manifest,'object':path}
        self.remote.update({path:payload_bytes,
                            'channels/central.json':canonical(self.sign('snapshot',channel))},
                           expected={'channels/central.json':canonical(envelope) if envelope else None})

    def _publish_full_worker(self,head,previous,envelope,manifest,data,payload_bytes,target_sha):
        error=None
        try:
            self._finish_snapshot_publication(head,previous,envelope,manifest,data,payload_bytes,target_sha)
        except Exception as failure:
            error={'stage':'publish_full','message':str(failure)}
        self._publish_worker_status={'state':'error' if error else 'ready',
                                     'started_at':self._publish_worker_status['started_at'],
                                     'finished_at':now(),'sequence':manifest['sequence'],
                                     'snapshot_id':manifest['snapshot_id'],
                                     'payload_sha256':manifest['payload_sha256'],'error':error}

    def publish_snapshot(self,head,*,background_full=False):
        previous,envelope=self.channel(head,'central','snapshot') if head else (None,None)
        central=self.config['central']; commit=central['code_commit']
        active=self.state/'software'/'active.json'
        if active.exists(): commit=read_json(active)['code_commit']
        # Materials must match the actual running approved board release.
        code_root=Path(read_json(active)['path']) if active.exists() else None
        def material(path):
            return read_json(code_root/path) if code_root else git_json(central['repo'],commit,path)
        payload=read_central(Path(central['ledger'])/'ledger.sqlite3',
            frozen_manifest=material('docs/a/source-manifest.json'),
            algorithms=material('docs/benchmarks/algorithm-registry.json'),code_commit=commit)
        if previous:
            prior_path=path_ok(previous.get('object'))
            if prior_path!='objects/'+previous['manifest'].get('payload_sha256',''):
                raise ValueError('Snapshot object identity mismatch')
            accepted=self.state/'accepted'/'current.json'
            try: accepted_manifest=read_json(accepted)
            except (OSError,ValueError,TypeError): accepted_manifest=None
            if accepted_manifest and accepted_manifest.get('snapshot_id')==previous['manifest'].get('snapshot_id'):
                old=self.accepted_payload(previous['manifest'])
            else:
                old=unpack(self.remote.read_path(head,previous['object']),previous['manifest'])
            reject_history_regression(old,payload)
            if old['snapshot_id']==payload['snapshot_id']:
                if (background_full and self._publish_worker_status['error'] and
                        (self._publish_thread is None or not self._publish_thread.is_alive()) and
                        previous['manifest']['snapshot_id']==self._publish_worker_status['snapshot_id'] and
                        previous['manifest']['payload_sha256']==self._publish_worker_status['payload_sha256']):
                    # An upload can succeed remotely but lose its HTTP response.
                    # The signed, fully verified central channel settles that uncertainty.
                    self._publish_worker_status={'state':'ready',
                        'started_at':self._publish_worker_status['started_at'],
                        'finished_at':now(),'sequence':previous['manifest']['sequence'],
                        'snapshot_id':previous['manifest']['snapshot_id'],
                        'payload_sha256':previous['manifest']['payload_sha256'],
                        'error':None}
                return
        published=publish_files(payload,self.state/'published')
        unchanged=published.get('unchanged',False)
        manifest={k:v for k,v in published.items() if k!='unchanged'}
        payload_bytes=(self.state/'published'/payload_name(manifest)).read_bytes()
        if unchanged:
            # The saved manifest and delta target must describe the same bytes.
            # A queued full checkpoint can leave this target ahead of central.
            payload=unpack(payload_bytes,manifest)
        data=pack_delta(old,payload) if previous else None
        target_sha=digest(canonical(payload)) if data is not None else None
        if previous and data is not None and self.config.get('git_fast_enabled',True):
            try: self.publish_git_fast_delta(previous,payload,manifest,data,
                                            target_canonical_sha256=target_sha)
            except Exception as error:
                self.errors.append({'stage':'git_fast_publish','message':str(error)})
        if not background_full:
            self._finish_snapshot_publication(head,previous,envelope,manifest,data,payload_bytes,target_sha)
            return
        if self._publish_thread is not None and self._publish_thread.is_alive(): return
        self._publish_worker_status={'state':'publishing','started_at':now(),'finished_at':None,
                                     'sequence':manifest['sequence'],
                                     'snapshot_id':manifest['snapshot_id'],
                                     'payload_sha256':manifest['payload_sha256'],'error':None}
        self._publish_thread=threading.Thread(target=self._publish_full_worker,
            args=(head,previous,envelope,manifest,data,payload_bytes,target_sha),
            name='benchmark-full-publisher',daemon=True)
        self._publish_thread.start()

    def publish_fast_delta(self,head,base_channel,base_payload,target,manifest,*,data=None,target_canonical_sha256=None):
        """Publish a small signed change before the legacy full object upload."""
        if data is None: data=pack_delta(base_payload,target)
        if data is None: return
        prior,prior_envelope=self.channel(head,'fast','snapshot-delta') if head else (None,None)
        if prior:
            prior_manifest=prior.get('target_manifest',{})
            if prior_manifest.get('sequence',-1)>manifest['sequence']:
                raise ValueError('Fast snapshot sequence rollback')
            if (prior_manifest.get('sequence')==manifest['sequence'] and
                    prior_manifest.get('records_sha256')!=manifest['records_sha256']):
                raise ValueError('Fast snapshot rewrote records at the same sequence')
            if prior_manifest==manifest: return
        object_path='deltas/'+digest(data)+'.json.gz'
        fast={'schema_version':1,'generation':prior['generation']+1 if prior else 1,
              'base_generation':base_channel['generation'],
              'base_manifest':base_channel['manifest'],'base_object':base_channel['object'],
              'target_manifest':manifest,'delta_object':object_path,
              'delta_sha256':digest(data),'delta_size':len(data),
              'target_canonical_sha256':target_canonical_sha256 or digest(canonical(target))}
        self.remote.update({object_path:data,
                            'channels/fast.json':canonical(self.sign('snapshot-delta',fast))},
                           expected={'channels/fast.json':canonical(prior_envelope) if prior_envelope else None})

    def git_fast_lane(self):
        if self._git_fast_lane is None:
            self._git_fast_lane=GitFastLane(self.state,self.remote.repository)
        return self._git_fast_lane

    def publish_git_fast_delta(self,base_channel,target,manifest,data,*,target_canonical_sha256=None):
        """Publish the same signed delta to a tiny, independently polled Git ref."""
        lane=self.git_fast_lane();head=lane.head()
        prior,prior_envelope=self.channel(head,'fast','snapshot-delta',remote=lane) if head else (None,None)
        if prior:
            prior_manifest=prior.get('target_manifest',{})
            if prior_manifest.get('sequence',-1)>manifest['sequence']:
                raise ValueError('Fast Git sequence rollback')
            if (prior_manifest.get('sequence')==manifest['sequence'] and
                    prior_manifest.get('records_sha256')!=manifest['records_sha256']):
                raise ValueError('Fast Git rewrote records at the same sequence')
            if prior_manifest==manifest: return
        object_path='deltas/'+digest(data)+'.json.gz'
        fast={'schema_version':1,'transport':'git','generation':prior['generation']+1 if prior else 1,
              'base_generation':base_channel['generation'],
              'base_manifest':base_channel['manifest'],'base_object':base_channel['object'],
              'target_manifest':manifest,'delta_object':object_path,
              'delta_sha256':digest(data),'delta_size':len(data),
              'target_canonical_sha256':target_canonical_sha256 or digest(canonical(target))}
        lane.update({'channels/fast.json':canonical(self.sign('snapshot-delta',fast)),object_path:data},
                    expected=canonical(prior_envelope) if prior_envelope else None)

    @staticmethod
    def _local_commit_files(repo,commit,paths,max_bytes=128*1024*1024):
        """Read a bounded set of regular blobs from an immutable local commit."""
        commit=fixed_sha(commit);paths=[path_ok(path) for path in paths]
        base=['git','-C',str(repo)]
        subprocess.run(base+['cat-file','-e',commit+'^{commit}'],stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,timeout=15,check=True)
        listing=subprocess.run(base+['ls-tree','-rz',commit,'--',*paths],stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,timeout=20,check=True).stdout
        entries={}
        for item in listing.split(b'\0'):
            if not item: continue
            meta,name=item.split(b'\t',1);mode,kind,sha=meta.decode('ascii').split(' ')
            name=name.decode('utf-8')
            if name not in paths or kind!='blob' or mode not in ('100644','100755'):
                raise ValueError('Local source is not a regular file: '+name)
            entries[name]=fixed_sha(sha)
        if set(entries)!=set(paths): raise FileNotFoundError('Local fixed commit is missing source files')
        object_ids=('\n'.join(entries.values())+'\n').encode('ascii')
        checked=subprocess.run(base+['cat-file','--batch-check'],input=object_ids,
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,check=True).stdout
        sizes={};total=0
        for name,line in zip(entries,checked.splitlines()):
            fields=line.decode('ascii').split()
            if len(fields)!=3 or fields[0]!=entries[name] or fields[1]!='blob':
                raise ValueError('Invalid local Git object size header')
            size=int(fields[2]);total+=size
            if size<0 or size>MAX_FILE or total>max_bytes:
                raise ValueError('Local fast-path artifact set exceeds size bound')
            sizes[name]=size
        if len(sizes)!=len(entries): raise ValueError('Incomplete local Git object size response')
        proc=subprocess.run(base+['cat-file','--batch'],input=object_ids,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=True)
        data=proc.stdout;offset=0;result={}
        for name,want in entries.items():
            end=data.find(b'\n',offset)
            if end<0: raise ValueError('Invalid local Git batch header')
            fields=data[offset:end].decode('ascii').split();offset=end+1
            if len(fields)!=3 or fields[0]!=want or fields[1]!='blob': raise ValueError('Local Git object identity mismatch')
            size=int(fields[2])
            if sizes.get(name)!=size: raise ValueError('Local Git object size changed')
            blob=data[offset:offset+size];offset+=size
            if len(blob)!=size or data[offset:offset+1]!=b'\n': raise ValueError('Truncated local Git object')
            offset+=1
            import hashlib
            if hashlib.sha1(b'blob '+str(size).encode()+b'\0'+blob).hexdigest()!=want:
                raise ValueError('Local Git blob hash mismatch')
            result[name]=blob
        return result

    def materialize_local_submission(self,entry,envelope):
        """Use the same signed submission to reach this machine's central inbox.

        The normal remote publication still runs. This only avoids sending a
        leader's own verified result through GitHub to its co-located ledger.
        """
        if self.role!='leader' or entry.get('payload',{}).get('actor')!=self.actor:
            return False
        with self.submission_lock(entry.get('id','')):
            return self._materialize_local_submission(entry,envelope)

    def _materialize_local_submission(self,entry,envelope):
        payload=self.verify(envelope,'submission')
        identity=digest(canonical(payload))
        if entry.get('id')!=identity: raise ValueError('Local fast-path submission identity mismatch')
        repo=entry.get('repo');commit=fixed_sha(payload.get('commit'));feed_path=path_ok(payload.get('feed'))
        target=Path(self.config['central']['inbox'])/identity
        if (target/'request.json').exists():
            prior=read_json(target/'request.json')
            source=prior.get('source',{}) if isinstance(prior,dict) else None
            if not isinstance(source,dict) or prior.get('id')!=identity or source.get('commit')!=commit:
                raise ValueError('Existing local inbox request has conflicting identity')
            return True
        if (target/'result.json').exists():
            prior=read_json(target/'result.json')
            if not isinstance(prior,dict) or prior.get('id')!=identity or prior.get('state') not in ('accepted','rejected'):
                raise ValueError('Existing local inbox result has conflicting identity')
            return True
        feed_bytes=self._local_commit_files(repo,commit,[feed_path])[feed_path]
        if len(feed_bytes)>MAX_FEED or digest(feed_bytes)!=payload.get('feed_sha256'):
            raise ValueError('Local fast-path feed hash mismatch')
        feed=json.loads(feed_bytes);refs=references(feed)
        if refs!=payload.get('artifacts'): raise ValueError('Local fast-path artifact manifest mismatch')
        producers={r.get('provenance',{}).get('producer_session','').split('/')[0].lower()
                   for r in feed['records']}
        if producers!={self.actor.lower()}: raise ValueError('Local fast-path producer identity mismatch')
        # Keep peak memory bounded for large complete feeds. The recursive
        # split only retries metadata and blob reads; artifacts are written as
        # soon as a bounded chunk has been verified. No request marker exists
        # until every file has passed its manifest hash check.
        def materialize_chunk(names):
            try:
                files=self._local_commit_files(repo,commit,names)
            except ValueError as error:
                if 'exceeds size bound' not in str(error) or len(names)<2: raise
                middle=len(names)//2
                materialize_chunk(names[:middle]);materialize_chunk(names[middle:])
                return
            for name in names:
                data=files[name]
                if digest(data)!=refs[name]: raise ValueError('Local fast-path artifact hash mismatch: '+name)
                atomic_write(target/'artifacts'/name,data)
        names=list(refs)
        for start in range(0,len(names),128): materialize_chunk(names[start:start+128])
        atomic_write(target/'feed.json',feed_bytes)
        source={'id':f'auto:{self.actor}:{identity}','repo':self.remote.repository,'commit':commit,
                'feed':feed_path,'path':feed_path,
                'url':f'https://github.com/{self.remote.repository}/blob/{commit}/{feed_path}'}
        write_json(target/'request.json',{'schema_version':1,'id':identity,'feed_file':'feed.json','source':source})
        return True

    def deliver_outbox(self,head,errors=None):
        if errors is None: errors=self.errors
        folder=self.state/'outbox'
        entries=list(folder.glob('*/entry.json'))
        # New result slices should join the transport promptly even while older
        # receipts are outstanding. FIFO by durable enqueue time remains stable
        # for the old work and is deterministic across restarts.
        def enqueue_key(path):
            try:
                item=read_json(path);queued=item.get('queued_at','')
                state=item.get('state')
                # A fresh complete feed must not sit behind hundreds of entries
                # whose immutable envelopes are already published and just await
                # a receipt. Those are cheaply reconciled from the central tree.
                group=0 if state in ('queued','publishing') else 1
                checked=item.get('last_checked_at') or item.get('last_attempt_at') or queued
                age=queued if group==0 else checked
                return (group,not isinstance(age,str),age if isinstance(age,str) else '',path.parent.name)
            except (OSError,ValueError,TypeError):
                return (2,True,'',path.parent.name)
        entries.sort(key=enqueue_key)
        pending={};parents=[];commit_presence={}
        checked_awaiting=0
        lane=submission_lane(self.actor)
        lane_head=self.remote.head(lane) if entries else None
        lane_tree=self.remote.tree(lane_head) if lane_head else {}
        # Receipt and legacy-submission presence are in this immutable head.
        # One cached tree lookup replaces one REST read per outbox entry.
        legacy_tree=self.remote.tree(head) if entries and head else {}
        def publish_pending():
            if not pending: return
            batch=dict(pending)
            batch_parents=tuple(dict.fromkeys(parents))
            try:
                # Each account owns a separate append-only lane. Small batches
                # amortize Git API calls without competing with other accounts'
                # mutable refs or the leader's central snapshot/receipt ref.
                self.remote.update({published:canonical(envelope)
                    for published,(_,envelope) in batch.items()},parents=batch_parents,branch=lane)
                for _,(path,_) in batch.items():
                    entry=read_json(path)
                    entry.update(state='awaiting_receipt',error=None,last_attempt_at=now())
                    write_json(path,entry)
            except Exception as error:
                for _,(path,_) in batch.items():
                    try:
                        entry=read_json(path)
                        entry.update(error=str(error),last_attempt_at=now())
                        write_json(path,entry)
                    except (OSError,ValueError,TypeError):
                        pass
                    errors.append({'stage':'upload','message':str(error)})
            finally:
                pending.clear();parents.clear()
        def ensure_fixed_commit(payload,entry):
            commit=payload['commit']
            if commit in commit_presence: return
            try:
                self.remote.request('GET','/git/commits/'+fixed_sha(commit))
                commit_presence[commit]=True
                return
            except RemoteError as error:
                if error.status!=404: raise
            ref='refs/heads/benchmark-delivery/'+self.actor+'/'+entry['id']
            subprocess.run(['git','-C',entry['repo'],'push','https://github.com/'+self.remote.repository+'.git',commit+':'+ref],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120,check=True)
            # Do not expose the source in the central ledger until its immutable
            # public URL is confirmed reachable from the organization repository.
            self.remote.request('GET','/git/commits/'+fixed_sha(commit))
            commit_presence[commit]=True
        for path in entries:
            try:
                entry=read_json(path)
                if not isinstance(entry,dict) or entry.get('id')!=path.parent.name or digest(canonical(entry['payload']))!=entry['id']:
                    raise ValueError('Malformed outbox identity')
                payload=entry['payload']
                if not isinstance(payload,dict): raise ValueError('Outbox payload must be an object')
                if not isinstance(entry.get('state'),str) or entry['state'] not in {'queued','publishing','awaiting_receipt','accepted','rejected'}:
                    raise ValueError('Outbox state missing or invalid')
                if not isinstance(entry.get('repo'),str) or not entry['repo']: raise ValueError('Outbox repository missing')
                if payload.get('schema_version')!=1: raise ValueError('Invalid outbox schema')
                fixed_sha(payload.get('commit'));path_ok(payload.get('feed'))
                if not isinstance(payload.get('feed_sha256'),str) or not re.fullmatch('[0-9a-f]{64}',payload['feed_sha256']):
                    raise ValueError('Outbox feed hash invalid')
                if not isinstance(payload.get('artifacts'),dict): raise ValueError('Outbox artifact map missing')
                for artifact,sha in payload['artifacts'].items():
                    path_ok(artifact)
                    if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha): raise ValueError('Outbox artifact hash invalid')
                if payload['actor']!=self.actor: raise ValueError('Outbox belongs to another actor')
            except (ValueError,KeyError,TypeError) as error:
                # Independent quarantine: one bad entry never stops valid neighbours.
                dest=self.state/'quarantine'/path.parent.name
                dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists(): dest=dest.with_name(dest.name+'-'+str(time.time_ns()))
                shutil.move(str(path.parent),dest)
                errors.append({'stage':'outbox','message':str(error)});continue
            if entry['state'] in ('accepted','rejected'): continue
            if entry['state']=='awaiting_receipt':
                # A short new-feed batch must be visible remotely before any
                # old receipt reconciliation starts. Otherwise the final
                # publish_pending() still lets old backlog delay new data.
                publish_pending()
                if checked_awaiting>=OUTBOX_RECEIPT_CHECK_BATCH_SIZE: continue
                checked_awaiting+=1
            try:
                receipt_path='receipts/'+self.actor+'/'+entry['id']+'.json'
                try: receipt=json.loads(self.remote.read(head,receipt_path)) if head and receipt_path in legacy_tree else None
                except FileNotFoundError: receipt=None
                if receipt:
                    result=self.verify(receipt,'receipt',central=True)
                    if result.get('id')!=entry['id'] or result.get('actor')!=self.actor or result.get('state') not in ('accepted','rejected'):
                        raise ValueError('Receipt identity/state mismatch')
                    entry.update(state=result['state'],receipt=result,error=None);write_json(path,entry);continue
                published='submissions/'+self.actor+'/'+entry['id']+'.json'
                is_published=published in lane_tree or published in legacy_tree
                if entry['state']=='awaiting_receipt' and is_published:
                    envelope=self.sign('submission',payload)
                    if self.role=='leader' and payload.get('actor')==self.actor:
                        ensure_fixed_commit(payload,entry)
                        try:
                            self._local_fastpath_status={'state':'syncing','delivery_id':entry['id'],
                                                         'started_at':now(),'finished_at':None,'error':None}
                            self.materialize_local_submission(entry,envelope)
                            self._local_fastpath_status={'state':'ready','delivery_id':entry['id'],
                                                         'started_at':self._local_fastpath_status['started_at'],
                                                         'finished_at':now(),'error':None}
                        except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
                            self._local_fastpath_status={'state':'fallback_remote','delivery_id':entry['id'],
                                'started_at':self._local_fastpath_status['started_at'],'finished_at':now(),
                                'error':str(error)}
                    # Presence in the immutable tree is enough here: the same
                    # writer already recorded successful publication. Do not read
                    # hundreds of unchanged envelopes merely to reassert it.
                    continue
                try:
                    if published in lane_tree: existing=json.loads(self.remote.read(lane_head,published))
                    elif published in legacy_tree: existing=json.loads(self.remote.read(head,published))
                    else: existing=None
                except FileNotFoundError: existing=None
                envelope=self.sign('submission',payload)
                if entry['state'] not in ('accepted','rejected') and self.role=='leader' and payload.get('actor')==self.actor:
                    ensure_fixed_commit(payload,entry)
                    try:
                        self._local_fastpath_status={'state':'syncing','delivery_id':entry['id'],
                                                     'started_at':now(),'finished_at':None,'error':None}
                        self.materialize_local_submission(entry,envelope)
                        self._local_fastpath_status={'state':'ready','delivery_id':entry['id'],
                                                     'started_at':self._local_fastpath_status['started_at'],
                                                     'finished_at':now(),'error':None}
                    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as error:
                        # Local acceleration is optional; the authenticated remote
                        # route remains authoritative and retries without data loss.
                        self._local_fastpath_status={'state':'fallback_remote','delivery_id':entry['id'],
                            'started_at':self._local_fastpath_status['started_at'],'finished_at':now(),
                            'error':str(error)}
                if existing:
                    if existing!=envelope: raise ValueError('Submission ID already has different bytes')
                    # The immutable envelope already exists. Its original batch may
                    # have reached GitHub just before a local crash.
                    entry.update(state='awaiting_receipt',error=None,last_attempt_at=now());write_json(path,entry)
                else:
                    ensure_fixed_commit(payload,entry)
                    pending[published]=(path,envelope);parents.append(payload['commit'])
                    if len(pending)>=OUTBOX_PUBLISH_BATCH_SIZE: publish_pending()
            except Exception as error:
                entry.update(error=str(error),last_attempt_at=now());write_json(path,entry)
                errors.append({'stage':'upload','message':str(error)})
            finally:
                if entry['state']=='awaiting_receipt' and path.exists():
                    # A bounded pass keeps new complete feeds from waiting for
                    # hundreds of old receipts. Rotating the last-check time
                    # gives every old submission another turn across cycles.
                    try:
                        checked=read_json(path)
                        checked['last_checked_at']=now()
                        write_json(path,checked)
                    except (OSError,ValueError,TypeError) as error:
                        errors.append({'stage':'outbox','message':str(error)})
        publish_pending()

    def upload_pass(self,known_record_ids):
        """Run one durable, single-writer local discovery and submission pass."""
        errors=[]
        def mark(stage):
            self._upload_status={'stage':stage,'started_at':self._upload_status['started_at'],
                                 'finished_at':None,'errors':self._upload_status['errors']}
        self._upload_status={'stage':'discover','started_at':now(),'finished_at':None,
                             'errors':self._upload_status['errors']}
        try:
            if self.config.get('watch_repositories'):
                errors.extend({'stage':'watch','message':e['error']} for e in discover(
                    self.state,self.config['watch_repositories'],self.actor,known_record_ids=known_record_ids))
            mark('deliver_outbox')
            self.deliver_outbox(self.remote.head(),errors)
        except Exception as error:
            errors.append({'stage':'upload','message':str(error)})
        finally:
            self._upload_status={'stage':'idle','started_at':self._upload_status['started_at'],
                                 'finished_at':now(),'errors':errors}

    def download_artifacts(self,commit,refs,target,deadline):
        missing=[]
        for name,sha in refs.items():
            dest=target/'artifacts'/name
            if not dest.exists() or digest(dest.read_bytes())!=sha: missing.append((name,sha,dest))
        def download(item):
            name,sha,dest=item
            reader=getattr(self.remote,'read_path',None)
            value=reader(commit,name) if reader else self.remote.read(commit,name)
            if digest(value)!=sha: raise ValueError('Artifact content hash mismatch: '+name)
            atomic_write(dest,value)
        # Only artifact GETs run concurrently; all signatures, Git writes, cursor updates
        # and final request publication remain on the owning thread. At most four
        # bounded reads are in flight and each verified file is durable across retries.
        index=0
        with ThreadPoolExecutor(max_workers=4,thread_name_prefix='benchmark-artifact') as pool:
            running=set()
            while running or index<len(missing):
                while len(running)<4 and index<len(missing) and time.monotonic()<=deadline:
                    running.add(pool.submit(download,missing[index]));index+=1
                if not running: break
                done,running=wait(running,return_when=FIRST_COMPLETED)
                for future in done: future.result()
        return index==len(missing)

    def receive_submissions(self,head,errors=None):
        if errors is None: errors=self.errors
        inbox=Path(self.config['central']['inbox'])
        central_tree=self.remote.tree(head) if head else {}
        progress_file=self.state/'receive-progress.json'
        try:
            progress=read_json(progress_file)
            if not isinstance(progress,dict): raise ValueError('Invalid receive cursor')
            if not isinstance(progress.get('verified_receipts',{}),dict): raise ValueError('Invalid receipt cache')
        except (OSError,ValueError,TypeError):
            # Scheduling hints are disposable; never repair ledger/snapshot history here.
            progress={}
        cache=progress.setdefault('verified_receipts',{})
        trust_id=digest(canonical(self.trusted))
        ordered=[];pending_count=0
        # Read legacy envelopes already committed to the old shared branch while
        # new submissions move to actor-owned lanes. This makes the ref migration
        # rolling-upgrade safe and drains existing history without rewriting it.
        for path in sorted(central_tree):
            if not path.startswith('submissions/') or not path.endswith('.json'): continue
            actor=path.split('/',2)[1]
            if actor not in self.trusted: continue
            receipt_path='receipts/'+path.removeprefix('submissions/')
            group='completed' if receipt_path in central_tree else 'pending'
            if group=='pending': pending_count+=1
            cursor_key=actor+':legacy:'+group
            ordered.append((actor,head,central_tree,group,cursor_key,path))
        lane_heads=self.remote.matching_heads('benchmark-submissions/')
        for actor in sorted(self.trusted):
            lane_head=lane_heads.get(submission_lane(actor))
            if not lane_head: continue
            lane_tree=self.remote.tree(lane_head)
            for path in sorted(lane_tree):
                if not path.startswith(f'submissions/{actor}/') or not path.endswith('.json'): continue
                receipt_path='receipts/'+path.removeprefix('submissions/')
                group='completed' if receipt_path in central_tree else 'pending'
                if group=='pending': pending_count+=1
                cursor_key=actor+':lane:'+group
                ordered.append((actor,lane_head,lane_tree,group,cursor_key,path))
        self.receive_status={'pending':pending_count,'budget_seconds':30 if pending_count>4 else 8}
        pending_buckets={};completed_buckets={}
        first_seen=progress.setdefault('first_seen',{})
        if not isinstance(first_seen,dict): first_seen={};progress['first_seen']=first_seen
        # snapshot.now() remains injectable in deterministic scheduler tests and
        # is persisted as a wall-clock timestamp so age survives process restarts.
        observed_at=datetime.fromisoformat(now()).timestamp()
        for actor,lane_head,lane_tree,group,cursor_key,path in ordered:
            cursor=progress.get(cursor_key,'')
            if not isinstance(cursor,str): cursor=''
            seen_key=cursor_key+'|'+path
            receipt_path='receipts/'+path.removeprefix('submissions/')
            if receipt_path in central_tree:
                first_seen.pop(seen_key,None)
            else:
                seen=first_seen.get(seen_key)
                if (isinstance(seen,bool) or not isinstance(seen,(int,float)) or seen<0
                        or seen>observed_at+30):
                    first_seen[seen_key]=observed_at
            item=(actor,lane_head,lane_tree,group,cursor_key,path,path>cursor)
            buckets=pending_buckets if group=='pending' else completed_buckets
            buckets.setdefault(cursor_key,[]).append(item)
        def round_robin(buckets,start):
            keys=sorted(buckets)
            if not keys:return [],keys
            start%=len(keys);keys=keys[start:]+keys[:start]
            queues={key:sorted(buckets[key],key=lambda item:(not item[6],item[5])) for key in keys}
            ordered_items=[];active=True
            while active:
                active=False
                for key in keys:
                    if queues[key]: ordered_items.append(queues[key].pop(0));active=True
            return ordered_items,keys
        pending_keys=sorted(pending_buckets)
        try: lane_rotation=progress.get('lane_rotation',0)
        except (TypeError,ValueError): lane_rotation=0
        if type(lane_rotation) is not int: lane_rotation=0
        pending_items,lane_keys=round_robin(pending_buckets,lane_rotation)
        completed_items,_=round_robin(completed_buckets,lane_rotation)
        fresh_cutoff=observed_at-30
        def split_fresh(items):
            fresh=[];old=[]
            for item in items:
                key=item[4]+'|'+item[5]
                (fresh if first_seen.get(key,0)>=fresh_cutoff else old).append(item)
            return fresh,old
        fresh_pending,old_pending=split_fresh(pending_items)
        fresh_completed,old_completed=split_fresh(completed_items)
        # Fresh pending submissions get a fast lane, but one old pending item is
        # admitted after every four fresh ones so continuous arrivals cannot starve
        # the durable backlog. Completed items remain lower priority than pending.
        scheduled=[]
        for offset in range(0,len(fresh_pending),4):
            scheduled.extend(fresh_pending[offset:offset+4])
            old_index=offset//4
            if old_index<len(old_pending): scheduled.append(old_pending[old_index])
        scheduled.extend(old_pending[(len(fresh_pending)+3)//4:])
        scheduled.extend(fresh_completed);scheduled.extend(old_completed)
        if lane_keys: progress['lane_rotation']=lane_rotation%len(lane_keys)
        deadline=time.monotonic()+self.receive_status['budget_seconds']
        seen_submissions={}
        for actor,lane_head,lane_tree,group,cursor_key,path,_is_new in scheduled:
            if time.monotonic()>deadline: break
            receipt_path='receipts/'+path.removeprefix('submissions/')
            submission_lock=None
            def blob_sha(name):
                entry=central_tree.get(name) if name.startswith('receipts/') else lane_tree.get(name)
                sha=entry.get('sha') if isinstance(entry,dict) else None
                return sha if isinstance(sha,str) and re.fullmatch('[0-9a-f]{40}',sha) else None
            submission_sha,receipt_sha=blob_sha(path),blob_sha(receipt_path)
            if path in seen_submissions:
                if seen_submissions[path]!=submission_sha:
                    errors.append({'stage':'receive','message':'Conflicting copies of one submission across transport refs','submission':path})
                continue
            seen_submissions[path]=submission_sha
            fingerprint=[submission_sha,receipt_sha,trust_id]
            if submission_sha and receipt_sha and cache.get(path)==fingerprint: continue
            progress[cursor_key]=path
            if group=='pending' and lane_keys:
                progress['lane_rotation']=(lane_keys.index(cursor_key)+1)%len(lane_keys)
            verified_delivery=False
            try:
                envelope=json.loads(self.remote.read(lane_head,path)); payload=self.verify(envelope,'submission')
                identity=digest(canonical(payload)); actor=envelope['issuer']
                if payload.get('actor')!=actor or path!=f'submissions/{actor}/{identity}.json':
                    raise ValueError('Submission path/actor identity mismatch')
                receipt_path=f'receipts/{actor}/{identity}.json'
                if receipt_path in central_tree:
                    prior=self.verify(json.loads(self.remote.read(head,receipt_path)),'receipt',central=True)
                    if prior.get('id')!=identity or prior.get('actor')!=actor or prior.get('state') not in ('accepted','rejected'):
                        raise ValueError('Receipt identity/state mismatch')
                    if submission_sha and receipt_sha: cache[path]=fingerprint
                    continue
                submission_lock=self.submission_lock(identity)
                submission_lock.acquire()
                target=inbox/identity; result_file=target/'result.json'
                if result_file.exists():
                    result=read_json(result_file)
                    if result.get('id')!=identity or result.get('state') not in ('accepted','rejected'): raise ValueError('Invalid board receipt')
                    result=dict(result,actor=actor,received_at=now())
                    self.remote.update({receipt_path:canonical(self.sign('receipt',result))},
                                       expected={receipt_path:None});continue
                if (target/'request.json').exists(): continue
                verified_delivery=True
                commit=fixed_sha(payload['commit']); feed_path=path_ok(payload['feed'])
                reader=getattr(self.remote,'read_path',None)
                data=reader(commit,feed_path) if reader else self.remote.read(commit,feed_path)
                if len(data)>MAX_FEED or digest(data)!=payload['feed_sha256']: raise ValueError('Feed hash mismatch')
                feed=json.loads(data); refs=references(feed)
                if refs!=payload['artifacts']: raise ValueError('Incomplete submission artifact manifest')
                producers={r.get('provenance',{}).get('producer_session','').split('/')[0].lower() for r in feed['records']}
                if producers!={actor}: raise ValueError('Feed producer session does not match signed uploader')
                # Retry-safe individual files; request.json is the sole visibility/commit marker.
                if not self.download_artifacts(commit,refs,target,deadline): return
                atomic_write(target/'feed.json',data)
                source={'id':f'auto:{actor}:{identity}','repo':self.remote.repository,'commit':commit,
                        'feed':feed_path,'path':feed_path,'url':f'https://github.com/{self.remote.repository}/blob/{commit}/{feed_path}'}
                write_json(target/'request.json',{'schema_version':1,'id':identity,'feed_file':'feed.json','source':source})
            except Exception as error:
                if verified_delivery and isinstance(error,(ValueError,KeyError,TypeError,FileNotFoundError)):
                    write_json(result_file,{'schema_version':1,'id':identity,'state':'rejected','receipt':None,'stage':'transport','error':str(error)})
                errors.append({'stage':'receive','message':str(error),'submission':path})
            finally:
                # Advance even on a partial download, rejection or transient error. A restart
                # must give the next pending batch a turn before retrying this one.
                if submission_lock is not None: submission_lock.release()
                write_json(progress_file,progress)

    def receive_pass(self,head):
        """Run one serialized inbox pass without holding up signed snapshot polling."""
        errors=[];started=now()
        self._receive_worker_status={'stage':'receive_submissions','started_at':started,
                                     'finished_at':None,'pending':self.receive_status.get('pending',0),'errors':[]}
        try:
            self.receive_submissions(head,errors)
        except Exception as error:
            errors.append({'stage':'receive','message':str(error)})
        finally:
            self._receive_worker_status={'stage':'idle','started_at':started,'finished_at':now(),
                'pending':self.receive_status.get('pending',0),'errors':errors[:20]}

    def outbox_counts(self):
        counts={}
        for path in (self.state/'outbox').glob('*/entry.json'):
            try:
                state=read_json(path)['state']
                if state in ('queued','publishing','awaiting_receipt','accepted','rejected'):
                    counts[state]=counts.get(state,0)+1
            except (OSError,ValueError,KeyError,TypeError): pass
        return counts

    def cycle(self,*,background_upload=False,background_receive=False,background_publish=False):
        self.errors=[]; status_path=self.state/'status.json'
        prior_publish_error=self._publish_worker_status['error'] if background_publish else None
        previous=read_json(status_path) if status_path.exists() else {}
        cycle_started=time.monotonic(); timings={}
        status={'schema_version':1,'role':self.role,'state':'syncing','last_attempt_at':now(),
                'last_success_at':previous.get('last_success_at'),'error':None,'data':previous.get('data',{}),
                'software':previous.get('software',{}),'upload':self.outbox_counts(),
                'transport':{'backend':'github-api+git-fast' if self.config.get('git_fast_enabled',True) else 'github-api',
                             'poll_seconds':self.config.get('poll_seconds',2)},
                'current_stage':None,'stage_started_at':None,'stage_timings_ms':{},
                'runtime_stage':previous.get('runtime_stage'),'runtime_stage_started_at':previous.get('runtime_stage_started_at'),
                'runtime_stage_timings_ms':previous.get('runtime_stage_timings_ms',{}),
                'local_fastpath':dict(self._local_fastpath_status)}
        write_json(status_path,status)
        def stage(name,operation):
            started=time.monotonic()
            status['current_stage']=name;status['stage_started_at']=now()
            status['stage_timings_ms']=dict(timings);write_json(status_path,status)
            try: return operation()
            finally:
                timings[name]=round((time.monotonic()-started)*1000,1)
                status['stage_timings_ms']=dict(timings)
                status['current_stage']=None;status['stage_started_at']=None
                status['cycle_elapsed_ms']=round((time.monotonic()-cycle_started)*1000,1)
                write_json(status_path,status)
        try:
            had_accepted=(self.state/'accepted/current.json').exists()
            fast_head=None;fast_lane=None;fast_error=None;fast_accepted=False
            if self.role!='leader' and had_accepted and self.config.get('git_fast_enabled',True):
                try:
                    fast_lane=self.git_fast_lane()
                    fast_head=stage('git_fast_head',fast_lane.head)
                    if fast_head:
                        stage('accept_git_fast_snapshot',lambda:self.accept_fast_snapshot(
                            fast_head,remote=fast_lane,base_head=None))
                        fast_accepted=True
                except Exception as error:
                    fast_error=error
            head=stage('remote_head',self.remote.head)
            if head and fast_head and not fast_accepted:
                try:
                    stage('accept_git_fast_snapshot',lambda:self.accept_fast_snapshot(
                        fast_head,remote=fast_lane,base_head=head))
                    fast_accepted=True;fast_error=None
                except Exception as error:
                    fast_error=error
            if fast_error is not None:
                self.errors.append({'stage':'git_fast_snapshot','message':str(fast_error)})
            if head and self.role!='leader' and had_accepted:
                try: stage('accept_fast_snapshot',lambda:self.accept_fast_snapshot(head))
                except Exception as error:
                    self.errors.append({'stage':'fast_snapshot','message':str(error)})
            if head: stage('accept_snapshot',lambda:self.accept_snapshot(head))
            if head and self.role!='leader' and not had_accepted:
                try:
                    if self.config.get('git_fast_enabled',True):
                        fast_lane=self.git_fast_lane()
                        fast_head=stage('git_fast_head',fast_lane.head)
                    if fast_head:
                        stage('accept_git_fast_snapshot',lambda:self.accept_fast_snapshot(
                            fast_head,remote=fast_lane,base_head=head))
                except Exception as error:
                    self.errors.append({'stage':'fast_snapshot','message':str(error)})
                try: stage('accept_fast_snapshot',lambda:self.accept_fast_snapshot(head))
                except Exception as error:
                    self.errors.append({'stage':'fast_snapshot','message':str(error)})
            if self.role=='leader':
                if background_receive:
                    if self._receive_thread is None or not self._receive_thread.is_alive():
                        self._receive_worker_status={'stage':'receive_submissions','started_at':now(),
                            'finished_at':None,'pending':self.receive_status.get('pending',0),'errors':[]}
                        self._receive_thread=threading.Thread(target=self.receive_pass,args=(head,),
                            name='benchmark-receiver',daemon=True)
                        self._receive_thread.start()
                    status['receive']=dict(self.receive_status)
                    status['receive_worker']=dict(self._receive_worker_status)
                else:
                    stage('receive_submissions',lambda:self.receive_submissions(head))
                    status['receive']=self.receive_status
                if background_publish:
                    stage('publish_snapshot',lambda:self.publish_snapshot(head,background_full=True))
                    status['publish_worker']=dict(self._publish_worker_status)
                    publish_error=(self._publish_worker_status['error'] or
                                   (prior_publish_error if self._publish_worker_status['state']=='publishing' else None))
                    if publish_error: self.errors.append(publish_error)
                else:
                    stage('publish_snapshot',lambda:self.publish_snapshot(head))
            if background_upload:
                if self._upload_thread is None or not self._upload_thread.is_alive():
                    # Only the polling thread touches the accepted snapshot cache.
                    # The upload worker gets an immutable ID set and owns all outbox writes.
                    known=self.accepted_record_ids() if self.config.get('watch_repositories') else None
                    self._upload_thread=threading.Thread(target=self.upload_pass,args=(known,),
                        name='benchmark-upload',daemon=True)
                    self._upload_thread.start()
                status['upload_worker']=dict(self._upload_status)
                self.errors.extend(status['upload_worker']['errors'])
            else:
                if self.config.get('watch_repositories'):
                    def scan_committed_feeds():
                        known=self.accepted_record_ids()
                        self.errors.extend({'stage':'watch','message':e['error']} for e in discover(
                            self.state,self.config['watch_repositories'],self.actor,known_record_ids=known))
                    stage('discover',scan_committed_feeds)
                stage('deliver_outbox',lambda:self.deliver_outbox(head))
            status['last_success_at']=now()
            status['state']='online' if not self.errors else 'error'
        except Exception as error:
            self.errors.append({'stage':'transport','message':str(error),'retry_after':getattr(error,'retry_after',0)})
            status['state']='offline'
        status['cycle_finished_at']=now()
        status['cycle_elapsed_ms']=round((time.monotonic()-cycle_started)*1000,1)
        status['stage_timings_ms']=dict(timings)
        status['current_stage']=None;status['stage_started_at']=None
        if self.errors: status['error']=self.errors[0]; status['errors']=self.errors[:20]
        current=self.state/'accepted'/'current.json'
        if current.exists():
            m=read_json(current); status['data']={k:m.get(k) for k in ('snapshot_id','sequence','record_count','generated_at','verified_at')}
        status['upload']=self.outbox_counts()
        status['local_fastpath']=dict(self._local_fastpath_status)
        software=self.state/'software'/'status.json'
        if software.exists(): status['software']=read_json(software)
        write_json(status_path,status)
        return status
