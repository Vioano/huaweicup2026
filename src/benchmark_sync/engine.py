"""Non-LLM durable bidirectional synchronization. The board remains the sole ledger writer."""
from __future__ import annotations
import json
import re
from pathlib import Path
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from .github import fixed_sha, path_ok, RemoteError
from .snapshot import (atomic_write, canonical, digest, now, read_central, publish_files,
                       unpack, reject_history_regression, payload_name, git_json)
from .submission import discover, references, MAX_FEED

OUTBOX_PUBLISH_BATCH_SIZE = 16


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
        self.receive_status={}
        self._accepted_cache_key=None
        self._accepted_payload_cache=None
        self._upload_thread=None
        self._upload_status={'stage':'idle','started_at':None,'finished_at':None,'errors':[]}
        self._receive_thread=None
        self._receive_worker_status={'stage':'idle','started_at':None,'finished_at':None,'pending':0,'errors':[]}

    def sign(self,domain,payload): return self.signatures.sign(domain,self.actor,payload,self.key)
    def verify(self,envelope,domain,*,central=False):
        keys={self.leader:self.trusted[self.leader]} if central else self.trusted
        return self.signatures.verify(envelope,domain=domain,trusted_keys=keys)

    def channel(self,head,name,domain):
        try: envelope=json.loads(self.remote.read(head,'channels/'+name+'.json'))
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
        data=self.remote.read(head,path); payload=unpack(data,manifest)
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

    def publish_snapshot(self,head):
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
                old=unpack(self.remote.read(head,previous['object']),previous['manifest'])
            reject_history_regression(old,payload)
            if old['snapshot_id']==payload['snapshot_id']: return
        manifest=publish_files(payload,self.state/'published')
        manifest={k:v for k,v in manifest.items() if k!='unchanged'}
        path='objects/'+manifest['payload_sha256']
        channel={'generation':(previous['generation']+1 if previous else 1),'manifest':manifest,'object':path}
        self.remote.update({path:(self.state/'published'/payload_name(manifest)).read_bytes(),
                            'channels/central.json':canonical(self.sign('snapshot',channel))},
                           expected={'channels/central.json':canonical(envelope) if envelope else None})

    def deliver_outbox(self,head,errors=None):
        if errors is None: errors=self.errors
        folder=self.state/'outbox'
        entries=sorted(folder.glob('*/entry.json'))
        pending={};parents=[];commit_presence={}
        lane=submission_lane(self.actor)
        lane_head=self.remote.head(lane) if entries else None
        lane_tree=self.remote.tree(lane_head) if lane_head else {}
        legacy_tree=None
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
            try:
                receipt_path='receipts/'+self.actor+'/'+entry['id']+'.json'
                try: receipt=json.loads(self.remote.read(head,receipt_path)) if head else None
                except FileNotFoundError: receipt=None
                if receipt:
                    result=self.verify(receipt,'receipt',central=True)
                    if result.get('id')!=entry['id'] or result.get('actor')!=self.actor or result.get('state') not in ('accepted','rejected'):
                        raise ValueError('Receipt identity/state mismatch')
                    entry.update(state=result['state'],receipt=result,error=None);write_json(path,entry);continue
                published='submissions/'+self.actor+'/'+entry['id']+'.json'
                if legacy_tree is None: legacy_tree=self.remote.tree(head) if head else {}
                try:
                    if published in lane_tree: existing=json.loads(self.remote.read(lane_head,published))
                    elif published in legacy_tree: existing=json.loads(self.remote.read(head,published))
                    else: existing=None
                except FileNotFoundError: existing=None
                envelope=self.sign('submission',payload)
                if existing:
                    if existing!=envelope: raise ValueError('Submission ID already has different bytes')
                    # The immutable envelope already exists. Its original batch may
                    # have reached GitHub just before a local crash.
                    entry.update(state='awaiting_receipt',error=None,last_attempt_at=now());write_json(path,entry)
                else:
                    if payload['commit'] not in commit_presence:
                        try:
                            self.remote.request('GET','/git/commits/'+fixed_sha(payload['commit']))
                            commit_presence[payload['commit']]=True
                        except RemoteError as error:
                            if error.status!=404: raise
                            # No mutable branch is overwritten. Each unique submission preserves its own Git commit.
                            ref='refs/heads/benchmark-delivery/'+self.actor+'/'+entry['id']
                            subprocess.run(['git','-C',entry['repo'],'push','https://github.com/'+self.remote.repository+'.git',payload['commit']+':'+ref],
                                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120,check=True)
                            commit_presence[payload['commit']]=True
                    pending[published]=(path,envelope);parents.append(payload['commit'])
                    if len(pending)>=OUTBOX_PUBLISH_BATCH_SIZE: publish_pending()
            except Exception as error:
                entry.update(error=str(error),last_attempt_at=now());write_json(path,entry)
                errors.append({'stage':'upload','message':str(error)})
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
            value=self.remote.read(commit,name)
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
        scheduled=[]
        for actor,lane_head,lane_tree,group,cursor_key,path in ordered:
            cursor=progress.get(cursor_key,'')
            if not isinstance(cursor,str): cursor=''
            scheduled.append((actor,lane_head,lane_tree,group,cursor_key,path,path>cursor))
        # Visit newly appended envelopes before cycling back over older transient failures.
        scheduled.sort(key=lambda item:(item[3]!='pending',item[4],not item[6],item[5]))
        deadline=time.monotonic()+self.receive_status['budget_seconds']
        seen_submissions={}
        for actor,lane_head,lane_tree,group,cursor_key,path,_is_new in scheduled:
            if time.monotonic()>deadline: break
            receipt_path='receipts/'+path.removeprefix('submissions/')
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
                target=inbox/identity; result_file=target/'result.json'
                if result_file.exists():
                    result=read_json(result_file)
                    if result.get('id')!=identity or result.get('state') not in ('accepted','rejected'): raise ValueError('Invalid board receipt')
                    result=dict(result,actor=actor,received_at=now())
                    self.remote.update({receipt_path:canonical(self.sign('receipt',result))});continue
                if (target/'request.json').exists(): continue
                verified_delivery=True
                commit=fixed_sha(payload['commit']); feed_path=path_ok(payload['feed'])
                data=self.remote.read(commit,feed_path)
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

    def cycle(self,*,background_upload=False,background_receive=False):
        self.errors=[]; status_path=self.state/'status.json'
        previous=read_json(status_path) if status_path.exists() else {}
        cycle_started=time.monotonic(); timings={}
        status={'schema_version':1,'role':self.role,'state':'syncing','last_attempt_at':now(),
                'last_success_at':previous.get('last_success_at'),'error':None,'data':previous.get('data',{}),
                'software':previous.get('software',{}),'upload':self.outbox_counts(),
                'transport':{'backend':'github-api','poll_seconds':self.config.get('poll_seconds',2)},
                'current_stage':None,'stage_started_at':None,'stage_timings_ms':{},
                'runtime_stage':previous.get('runtime_stage'),'runtime_stage_started_at':previous.get('runtime_stage_started_at'),
                'runtime_stage_timings_ms':previous.get('runtime_stage_timings_ms',{})}
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
            head=stage('remote_head',self.remote.head)
            if head: stage('accept_snapshot',lambda:self.accept_snapshot(head))
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
        software=self.state/'software'/'status.json'
        if software.exists(): status['software']=read_json(software)
        write_json(status_path,status)
        return status
