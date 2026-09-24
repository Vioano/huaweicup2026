from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from src.benchmark_sync.engine import Engine, write_json, read_json
from src.benchmark_sync.snapshot import canonical, digest, snapshot_id, unpack
from src.benchmark_sync.snapshot import publish_files, read_central
from src.benchmark_sync.signing import Signatures
from src.benchmark_sync.github import RemoteError
from src.benchmark_sync.git_fast import GitFastLane
from src.benchmark_sync.delta import pack_delta

class Remote:
    repository='test/repository'
    def __init__(self): self.commits={};self.current=None;self.branches={};self.fail_path=None
    def head(self,branch=None): return self.current if branch is None else self.branches.get(branch)
    def matching_heads(self,prefix): return {name:sha for name,sha in self.branches.items() if name.startswith(prefix)}
    def tree(self,commit): return {p:{'sha':hashlib.sha1(b'blob '+str(len(v)).encode()+b'\0'+v).hexdigest()} for p,v in self.commits[commit].items()}
    def read(self,commit,path):
        if path==self.fail_path: raise RemoteError(503)
        if commit not in self.commits or path not in self.commits[commit]: raise FileNotFoundError(path)
        return self.commits[commit][path]
    def read_path(self,commit,path): return self.read(commit,path)
    def update(self,files,parents=(),expected=None,branch=None):
        head=self.current if branch is None else self.branches.get(branch)
        values=dict(self.commits.get(head,{}));values.update(files)
        for path,want in (expected or {}).items():
            current=self.commits.get(head,{}).get(path)
            if current!=want: raise RuntimeError('Channel changed before publication; rebuild against latest generation')
        commit=hashlib.sha1(canonical({p:digest(v) for p,v in values.items()})).hexdigest()
        self.commits[commit]=values
        if branch is None:self.current=commit
        else:self.branches[branch]=commit
        return commit
    def request(self,method,path):
        if path.rsplit('/',1)[-1] not in self.commits: raise RemoteError(404)
        return {}


def snapshot_payload(count):
    records=[{'id':f'{i:064x}','attempt_id':f'attempt-{i}','revision':1,
              'problem':'P1','case_id':'001','cores':1,'metrics':{'makespan_cycles':i},
              'eligible':True,'sequence':i} for i in range(1,count+1)]
    payload={'schema_version':1,'generated_at':f'2026-09-24T20:00:{count:02d}+00:00',
             'central_url':'https://github.com/test/repository','sequence':count,
             'records':records,'source_status':{},'manifest':{},'algorithms':{},
             'publisher':{'actor':'leader','board_code_commit':'a'*40}}
    payload['record_count']=count
    payload['record_ids_sha256']=digest(('\n'.join(sorted(r['id'] for r in records))+'\n').encode())
    payload['records_sha256']=digest(canonical(records))
    payload['snapshot_id']=snapshot_id(payload)
    return payload

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.remote=Remote();self.sign=Signatures()
        self.keys={a:self.sign.generate(self.root/(a+'.pem')) for a in ('leader','member')}
        self.configs={a:{'state':str(self.root/a),'actor':a,'leader':'leader','role':a if a=='leader' else 'member',
                     'trusted_keys':self.keys,'private_key':str(self.root/(a+'.pem')),
                     'git_fast_enabled':False} for a in self.keys}
        self.engines={a:Engine(c,self.remote,self.sign) for a,c in self.configs.items()}
        self.engines['leader'].config['central']={'inbox':str(self.root/'inbox')}
    def tearDown(self): self.tmp.cleanup()
    def queue(self,actor='member',nonce=None):
        artifact=b'{"test":true}';session=actor+'/s-test'+('' if nonce is None else '-'+str(nonce))
        feed={'schema_version':1,'records':[{'provenance':{'producer_session':session},'artifacts':{'plan':{'path':'results/plan.json','sha256':digest(artifact)}}}]}
        feed_bytes=canonical(feed);commit='a'*40 if nonce is None else hashlib.sha1(str(nonce).encode()).hexdigest()
        self.remote.commits[commit]={'results/board-feed.json':feed_bytes,'results/plan.json':artifact}
        payload={'schema_version':1,'actor':actor,'commit':commit,'feed':'results/board-feed.json',
                 'feed_sha256':digest(feed_bytes),'artifacts':{'results/plan.json':digest(artifact)}}
        identity=digest(canonical(payload));p=self.root/actor/'outbox'/identity/'entry.json'
        write_json(p,{'id':identity,'payload':payload,'state':'queued','repo':str(self.root)})
        return p,identity
    def test_member_upload_central_inbox_and_signed_receipt(self):
        p,identity=self.queue();member=self.engines['member'];leader=self.engines['leader']
        member.deliver_outbox(None);self.assertEqual(read_json(p)['state'],'awaiting_receipt')
        leader.receive_submissions(self.remote.head())
        request=read_json(self.root/'inbox'/identity/'request.json')
        self.assertEqual(request['id'],identity)
        write_json(self.root/'inbox'/identity/'result.json',{'schema_version':1,'id':identity,'state':'accepted','receipt':{'added':1},'error':None})
        leader.receive_submissions(self.remote.head());member.deliver_outbox(self.remote.head())
        self.assertEqual(read_json(p)['state'],'accepted')
        before=self.remote.head();member.deliver_outbox(before);leader.receive_submissions(before)
        self.assertEqual(before,self.remote.head())

    def test_new_feed_precedes_bounded_old_receipt_checks_without_starvation(self):
        from src.benchmark_sync.engine import OUTBOX_RECEIPT_CHECK_BATCH_SIZE
        member=self.engines['member']
        old=[self.queue(nonce=n) for n in range(OUTBOX_RECEIPT_CHECK_BATCH_SIZE*2+1)]
        member.deliver_outbox(None)
        self.assertTrue(all(read_json(path)['state']=='awaiting_receipt' for path,_ in old))
        fresh,fresh_id=self.queue(nonce=9999)
        member.deliver_outbox(None)
        self.assertEqual(read_json(fresh)['state'],'awaiting_receipt')
        self.assertIn(f'submissions/member/{fresh_id}.json',self.remote.tree(self.remote.head('benchmark-submissions/member')))
        self.assertEqual(sum('last_checked_at' in read_json(path) for path,_ in old),OUTBOX_RECEIPT_CHECK_BATCH_SIZE)
        member.deliver_outbox(None)
        member.deliver_outbox(None)
        self.assertTrue(all('last_checked_at' in read_json(path) for path,_ in old))

    def test_short_new_batch_is_published_before_reading_old_receipts(self):
        from unittest.mock import patch
        member=self.engines['member'];leader=self.engines['leader']
        old=[self.queue(nonce=n) for n in range(33)]
        member.deliver_outbox(None)
        old_path,old_id=min(old,key=lambda pair:(read_json(pair[0])['last_attempt_at'],pair[0].parent.name))
        receipt_path=f'receipts/member/{old_id}.json'
        receipt=leader.sign('receipt',{'id':old_id,'actor':'member','state':'accepted',
                                       'received_at':'2026-09-24T20:00:00Z'})
        self.remote.update({receipt_path:canonical(receipt)})
        fresh,fresh_id=self.queue(nonce=9999)
        new_path=f'submissions/member/{fresh_id}.json'
        events=[];original_update=self.remote.update;original_read=self.remote.read
        def recorded_update(files,**kwargs):
            if new_path in files: events.append('new_published')
            return original_update(files,**kwargs)
        def recorded_read(commit,path):
            if path==receipt_path: events.append('old_receipt_read')
            return original_read(commit,path)
        with patch.object(self.remote,'update',side_effect=recorded_update), \
             patch.object(self.remote,'read',side_effect=recorded_read):
            member.deliver_outbox(self.remote.head())
        self.assertEqual(read_json(fresh)['state'],'awaiting_receipt')
        self.assertEqual(read_json(old_path)['state'],'accepted')
        self.assertLess(events.index('new_published'),events.index('old_receipt_read'))

    def test_leader_local_fastpath_validates_fixed_commit_and_keeps_remote_delivery(self):
        import os,subprocess
        repo=self.root/'source';repo.mkdir()
        subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'config','user.name','Sync Test'],check=True)
        subprocess.run(['git','-C',str(repo),'config','user.email','sync-test@example.invalid'],check=True)
        artifact=b'{"fixed":"plan"}';feed={'schema_version':1,'records':[{
            'provenance':{'producer_session':'leader/s-local-fastpath'},
            'artifacts':{'plan':{'path':'results/plan.json','sha256':digest(artifact)}}}]}
        feed_bytes=canonical(feed);(repo/'results').mkdir();(repo/'results/plan.json').write_bytes(artifact)
        (repo/'results/board-feed.json').write_bytes(feed_bytes)
        subprocess.run(['git','-C',str(repo),'add','results'],check=True)
        env=dict(os.environ,GIT_AUTHOR_NAME='Sync Test',GIT_AUTHOR_EMAIL='sync-test@example.invalid',
                 GIT_COMMITTER_NAME='Sync Test',GIT_COMMITTER_EMAIL='sync-test@example.invalid')
        subprocess.run(['git','-C',str(repo),'commit','-qm','fixed benchmark feed'],check=True,env=env)
        commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        self.remote.commits[commit]={'results/board-feed.json':feed_bytes,'results/plan.json':artifact}
        payload={'schema_version':1,'actor':'leader','commit':commit,'feed':'results/board-feed.json',
                 'feed_sha256':digest(feed_bytes),'artifacts':{'results/plan.json':digest(artifact)}}
        identity=digest(canonical(payload));entry_path=self.root/'leader'/'outbox'/identity/'entry.json'
        write_json(entry_path,{'id':identity,'payload':payload,'state':'queued','repo':str(repo)})
        leader=self.engines['leader'];leader.deliver_outbox(None)
        request=read_json(self.root/'inbox'/identity/'request.json')
        self.assertEqual(request['id'],identity)
        self.assertEqual((self.root/'inbox'/identity/'artifacts/results/plan.json').read_bytes(),artifact)
        self.assertIn(f'submissions/leader/{identity}.json',self.remote.tree(self.remote.head('benchmark-submissions/leader')))
        self.assertEqual(read_json(entry_path)['state'],'awaiting_receipt')
        from concurrent.futures import ThreadPoolExecutor
        envelope=leader.sign('submission',payload)
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda _:leader.materialize_local_submission(read_json(entry_path),envelope),range(2))),[True,True])
        # A durable request was published only after its artifacts passed the
        # checks above. Reconciliation must still work if an old source worktree
        # has since been removed.
        old_entry=dict(read_json(entry_path),repo=str(self.root/'removed-source'))
        self.assertTrue(leader.materialize_local_submission(old_entry,envelope))
        bad_payload=dict(payload,artifacts={'results/plan.json':'0'*64})
        bad_entry={'id':digest(canonical(bad_payload)),'payload':bad_payload,'repo':str(repo)}
        with self.assertRaisesRegex(ValueError,'artifact manifest'):
            leader.materialize_local_submission(bad_entry,leader.sign('submission',bad_payload))

    def test_member_cannot_use_local_fastpath(self):
        engine=self.engines['leader'];engine.config['central']={'inbox':str(self.root/'inbox')}
        entry={'id':'x','payload':{'actor':'member'}}
        self.assertFalse(engine.materialize_local_submission(entry,{}))

    def test_local_fastpath_waits_for_fixed_commit_to_be_publicly_reachable(self):
        import os,subprocess
        from unittest.mock import patch
        repo=self.root/'source-unreachable';repo.mkdir()
        subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'config','user.name','Sync Test'],check=True)
        subprocess.run(['git','-C',str(repo),'config','user.email','sync-test@example.invalid'],check=True)
        artifact=b'{}';feed={'schema_version':1,'records':[{
            'provenance':{'producer_session':'leader/s-source-reachability'},
            'artifacts':{'plan':{'path':'results/plan.json','sha256':digest(artifact)}}}]}
        feed_bytes=canonical(feed);(repo/'results').mkdir();(repo/'results/plan.json').write_bytes(artifact)
        (repo/'results/board-feed.json').write_bytes(feed_bytes)
        subprocess.run(['git','-C',str(repo),'add','results'],check=True)
        env=dict(os.environ,GIT_AUTHOR_NAME='Sync Test',GIT_AUTHOR_EMAIL='sync-test@example.invalid',
                 GIT_COMMITTER_NAME='Sync Test',GIT_COMMITTER_EMAIL='sync-test@example.invalid')
        subprocess.run(['git','-C',str(repo),'commit','-qm','fixed benchmark feed'],check=True,env=env)
        commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        payload={'schema_version':1,'actor':'leader','commit':commit,'feed':'results/board-feed.json',
                 'feed_sha256':digest(feed_bytes),'artifacts':{'results/plan.json':digest(artifact)}}
        identity=digest(canonical(payload));entry_path=self.root/'leader'/'outbox'/identity/'entry.json'
        write_json(entry_path,{'id':identity,'payload':payload,'state':'queued','repo':str(repo)})
        leader=self.engines['leader'];inbox=self.root/'inbox'/identity
        with patch('src.benchmark_sync.engine.subprocess.run',side_effect=subprocess.CalledProcessError(1,['git','push'])):
            leader.deliver_outbox(None)
        self.assertFalse((inbox/'request.json').exists())
        self.assertEqual(read_json(entry_path)['state'],'queued')
        self.remote.commits[commit]={'results/board-feed.json':feed_bytes,'results/plan.json':artifact}
        leader.deliver_outbox(None)
        self.assertTrue((inbox/'request.json').exists())

    def test_local_fastpath_splits_artifact_reads_when_batch_exceeds_memory_bound(self):
        import os,subprocess
        from unittest.mock import patch
        repo=self.root/'source-large-feed';repo.mkdir()
        subprocess.run(['git','init','-q',str(repo)],check=True)
        subprocess.run(['git','-C',str(repo),'config','user.name','Sync Test'],check=True)
        subprocess.run(['git','-C',str(repo),'config','user.email','sync-test@example.invalid'],check=True)
        artifacts={f'results/part-{n}.json':f'{{"part":{n}}}'.encode() for n in range(3)}
        records=[{'provenance':{'producer_session':'leader/s-large-feed'},
                  'artifacts':{'result':{'path':name,'sha256':digest(data)}}}
                 for name,data in artifacts.items()]
        feed_bytes=canonical({'schema_version':1,'records':records})
        for name,data in artifacts.items():
            path=repo/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        (repo/'results/board-feed.json').write_bytes(feed_bytes)
        subprocess.run(['git','-C',str(repo),'add','results'],check=True)
        env=dict(os.environ,GIT_AUTHOR_NAME='Sync Test',GIT_AUTHOR_EMAIL='sync-test@example.invalid',
                 GIT_COMMITTER_NAME='Sync Test',GIT_COMMITTER_EMAIL='sync-test@example.invalid')
        subprocess.run(['git','-C',str(repo),'commit','-qm','fixed benchmark feed'],check=True,env=env)
        commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        payload={'schema_version':1,'actor':'leader','commit':commit,'feed':'results/board-feed.json',
                 'feed_sha256':digest(feed_bytes),'artifacts':{name:digest(data) for name,data in artifacts.items()}}
        identity=digest(canonical(payload));entry={'id':identity,'payload':payload,'repo':str(repo)}
        leader=self.engines['leader'];original=Engine._local_commit_files
        def bounded(repo_arg,commit_arg,paths,max_bytes=128*1024*1024):
            if len(paths)>1: raise ValueError('Local fast-path artifact set exceeds size bound')
            return original(repo_arg,commit_arg,paths,max_bytes)
        with patch.object(Engine,'_local_commit_files',side_effect=bounded):
            self.assertTrue(leader.materialize_local_submission(entry,leader.sign('submission',payload)))
        for name,data in artifacts.items(): self.assertEqual((self.root/'inbox'/identity/'artifacts'/name).read_bytes(),data)
        self.assertTrue((self.root/'inbox'/identity/'request.json').exists())

    def test_small_feeds_keep_individual_signatures_in_bounded_transport_batches(self):
        from unittest.mock import patch
        member=self.engines['member'];items=[self.queue(nonce=i) for i in range(35)]
        original=self.remote.update;calls=[]
        def count_update(files,**kwargs):
            calls.append((set(files),kwargs.get('parents',())))
            return original(files,**kwargs)
        with patch.object(self.remote,'update',side_effect=count_update):
            member.deliver_outbox(None)
        self.assertEqual([len(files) for files,_ in calls],[16,16,3])
        self.assertEqual(sum(len(files) for files,_ in calls),35)
        tree=self.remote.tree(self.remote.head('benchmark-submissions/member'))
        self.assertEqual(sum(p.startswith('submissions/member/') for p in tree),35)
        for entry,_ in items:self.assertEqual(read_json(entry)['state'],'awaiting_receipt')

    def test_new_queued_feed_uploads_before_old_receipt_backlog(self):
        from unittest.mock import patch
        member=self.engines['member'];old=[self.queue(nonce=f'backlog-{i}') for i in range(24)]
        member.deliver_outbox(None)
        for path,_ in old:
            item=read_json(path);item.update(state='awaiting_receipt',queued_at='2026-09-01T00:00:00Z');write_json(path,item)
        newest=self.queue(nonce='fresh-arrival')
        calls=[];update=self.remote.update
        def record(files,**kwargs):
            calls.append(tuple(files));return update(files,**kwargs)
        with patch.object(self.remote,'update',side_effect=record):
            member.deliver_outbox(self.remote.head())
        self.assertTrue(calls)
        self.assertEqual(calls[0],(f'submissions/member/{newest[1]}.json',))
        self.assertEqual(read_json(newest[0])['state'],'awaiting_receipt')
        for path,_ in old:self.assertEqual(read_json(path)['state'],'awaiting_receipt')
    def test_leader_can_also_submit_and_neighbour_corruption_is_isolated(self):
        p,identity=self.queue('leader');bad=self.root/'leader'/'outbox'/'broken'/'entry.json';bad.parent.mkdir(parents=True);bad.write_text('{')
        leader=self.engines['leader'];leader.deliver_outbox(None)
        self.assertEqual(read_json(p)['state'],'awaiting_receipt');self.assertTrue((self.root/'leader'/'quarantine'/'broken').exists())
        leader.receive_submissions(self.remote.head());self.assertTrue((self.root/'inbox'/identity/'request.json').exists())

    def test_leader_reads_legacy_shared_ref_while_new_writes_use_actor_lane(self):
        entry,identity=self.queue();payload=read_json(entry)['payload']
        legacy=f'submissions/member/{identity}.json'
        self.remote.update({legacy:canonical(self.engines['member'].sign('submission',payload))})
        self.engines['leader'].receive_submissions(self.remote.head())
        self.assertTrue((self.root/'inbox'/identity/'request.json').exists())
        self.assertIsNone(self.remote.head('benchmark-submissions/member'))

    def test_same_submission_in_legacy_and_actor_lane_publishes_receipt_once(self):
        from unittest.mock import patch
        entry,identity=self.queue();payload=read_json(entry)['payload'];member=self.engines['member']
        member.deliver_outbox(None)
        legacy=f'submissions/member/{identity}.json'
        envelope=canonical(member.sign('submission',payload))
        self.remote.update({legacy:envelope})
        target=self.root/'inbox'/identity
        write_json(target/'result.json',{'schema_version':1,'id':identity,'state':'accepted','receipt':{'added':1},'error':None})
        original=self.remote.update;published=[];expected_refs=[]
        def record(files,**kwargs):
            published.extend(path for path in files if path==f'receipts/member/{identity}.json')
            expected_refs.append(kwargs.get('expected'))
            return original(files,**kwargs)
        with patch.object(self.remote,'update',side_effect=record):
            self.engines['leader'].receive_submissions(self.remote.head())
        self.assertEqual(published,[f'receipts/member/{identity}.json'])
        self.assertEqual(expected_refs,[{f'receipts/member/{identity}.json':None}])
        self.assertIn(f'receipts/member/{identity}.json',self.remote.tree(self.remote.head()))

    def test_concurrent_existing_receipt_is_never_overwritten(self):
        from unittest.mock import patch
        entry,identity=self.queue();payload=read_json(entry)['payload'];member=self.engines['member']
        member.deliver_outbox(None)
        write_json(self.root/'inbox'/identity/'result.json',{'schema_version':1,'id':identity,'state':'accepted','receipt':{'added':1},'error':None})
        path=f'receipts/member/{identity}.json';original=self.remote.update;existing=None
        def race(files,**kwargs):
            nonlocal existing
            if path in files and existing is None:
                competing={'id':identity,'actor':'member','state':'accepted','received_at':'2026-09-24T20:00:00Z'}
                existing=canonical(self.engines['leader'].sign('receipt',competing))
                original({path:existing})
            return original(files,**kwargs)
        with patch.object(self.remote,'update',side_effect=race):
            self.engines['leader'].receive_submissions(self.remote.head())
        self.assertEqual(self.remote.read(self.remote.head(),path),existing)
    def test_interrupted_download_never_exposes_partial_submission(self):
        p,identity=self.queue();self.engines['member'].deliver_outbox(None)
        self.remote.fail_path='results/plan.json';leader=self.engines['leader'];leader.receive_submissions(self.remote.head())
        self.assertFalse((self.root/'inbox'/identity/'request.json').exists())
        self.remote.fail_path=None;leader.receive_submissions(self.remote.head())
        self.assertTrue((self.root/'inbox'/identity/'request.json').exists())
    def test_authenticated_bad_bytes_return_rejection_instead_of_waiting_forever(self):
        p,identity=self.queue();self.engines['member'].deliver_outbox(None)
        self.remote.commits['a'*40]['results/plan.json']=b'changed'
        leader=self.engines['leader'];leader.receive_submissions(self.remote.head())
        self.assertFalse((self.root/'inbox'/identity/'request.json').exists())
        leader.receive_submissions(self.remote.head());self.engines['member'].deliver_outbox(self.remote.head())
        self.assertEqual(read_json(p)['state'],'rejected')

    def test_signed_json_structure_errors_get_durable_rejection(self):
        cases=[[], None, 1, {'schema_version':1,'records':[None]},
               {'schema_version':1,'records':[{'provenance':[]}]},
               {'schema_version':1,'records':[{'provenance':{'producer_session':None}}]}]
        for feed in cases:
            with self.subTest(feed=feed):
                raw=canonical(feed);commit='a'*40
                self.remote.commits[commit]={'results/board-feed.json':raw}
                payload={'schema_version':1,'actor':'member','commit':commit,'feed':'results/board-feed.json','feed_sha256':digest(raw),'artifacts':{}}
                identity=digest(canonical(payload));path=f'submissions/member/{identity}.json'
                self.remote.update({path:canonical(self.engines['member'].sign('submission',payload))},branch='benchmark-submissions/member')
                leader=self.engines['leader'];leader.receive_submissions(self.remote.head());leader.receive_submissions(self.remote.head())
                result=read_json(self.root/'inbox'/identity/'result.json')
                self.assertEqual(result['state'],'rejected')
                self.assertIn(f'receipts/member/{identity}.json',self.remote.tree(self.remote.head()))

    def test_missing_state_is_quarantined_without_blocking_valid_neighbour(self):
        good,_=self.queue();bad=read_json(good);del bad['state']
        bad['payload']=dict(bad['payload'],feed='results/bad-feed.json')
        bad['id']=digest(canonical(bad['payload']))
        path=self.root/'member'/'outbox'/bad['id']/'entry.json';write_json(path,bad)
        self.engines['member'].deliver_outbox(None)
        self.assertTrue((self.root/'member'/'quarantine'/bad['id']).exists())
        self.assertEqual(read_json(good)['state'],'awaiting_receipt')

    def test_untrusted_submitter_never_reaches_ledger(self):
        p,identity=self.queue();self.engines['member'].deliver_outbox(None)
        self.engines['leader'].trusted={'leader':self.keys['leader']}
        self.engines['leader'].receive_submissions(self.remote.head())
        self.assertFalse((self.root/'inbox'/identity/'request.json').exists())

    def scheduler_fixture(self,count=64):
        # Signature validation is covered separately; virtual 2 s validations reproduce
        # a long receipt prefix without sleeping or producing research data.
        items=[]
        for nonce in range(count):
            payload={'actor':'member','nonce':nonce}
            identity=digest(canonical(payload));path=f'submissions/member/{identity}.json'
            items.append((path,identity,payload))
        items.sort()
        files={p:canonical({'issuer':'member','payload':v}) for p,_,v in items}
        receipts={}
        for _,identity,_ in items[:-1]:
            receipts[f'receipts/member/{identity}.json']=canonical({'payload':{'id':identity,'actor':'member','state':'accepted'}})
        self.remote.update(files,branch='benchmark-submissions/member')
        self.remote.update(receipts)
        return items

    def test_completed_prefix_cannot_starve_new_submission(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        items=self.scheduler_fixture();leader=self.engines['leader'];clock=[0];visited=[]
        def verify(envelope,domain,**kwargs):
            clock[0]+=2
            if domain=='submission':visited.append(digest(canonical(envelope['payload'])))
            return envelope['payload']
        leader.verify=verify
        with patch('src.benchmark_sync.engine.time',SimpleNamespace(monotonic=lambda:clock[0])):
            leader.receive_submissions(self.remote.head())
        pending_id=items[-1][1]
        self.assertEqual(visited[0],pending_id)
        self.assertEqual(read_json(self.root/'inbox'/pending_id/'result.json')['state'],'rejected')

    def test_new_submission_overtakes_old_pending_but_old_work_gets_a_turn(self):
        from datetime import datetime,timezone,timedelta
        from unittest.mock import patch
        old=[self.queue(nonce=f'old-{i}') for i in range(8)]
        newest=self.queue(nonce='newest')
        member=self.engines['member'];member.deliver_outbox(None)
        leader=self.engines['leader']
        lane='benchmark-submissions/member';head=self.remote.head(lane)
        current=datetime.now(timezone.utc).timestamp()
        progress={'first_seen':{f'member:lane:pending|submissions/member/{identity}.json':current-90
                                for _,identity in old}}
        write_json(self.root/'leader'/'receive-progress.json',progress)
        visited=[];original=leader.verify
        def observe(envelope,domain,**kwargs):
            if domain=='submission':visited.append(digest(canonical(envelope['payload'])))
            return original(envelope,domain,**kwargs)
        with patch.object(leader,'verify',side_effect=observe):
            leader.receive_submissions(self.remote.head())
        self.assertEqual(visited[0],newest[1])
        self.assertIn(old[0][1],visited)

    def test_partial_batch_yields_to_next_pending_after_restart(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        p,identity=self.queue();self.engines['member'].deliver_outbox(None)
        payload=read_json(p)['payload'];other=dict(payload,nonce='second')
        other_id=digest(canonical(other))
        self.remote.update({f'submissions/member/{other_id}.json':canonical(self.engines['member'].sign('submission',other))},branch='benchmark-submissions/member')
        identities=sorted([identity,other_id]);clock=[0];visited=[]
        for expected in identities:
            leader=Engine(self.configs['leader'],self.remote,self.sign)
            original=leader.verify
            def slow_verify(envelope,domain,**kwargs):
                result=original(envelope,domain,**kwargs)
                if domain=='submission':
                    clock[0]+=9;visited.append(digest(canonical(result)))
                return result
            leader.verify=slow_verify
            with patch('src.benchmark_sync.engine.time',SimpleNamespace(monotonic=lambda:clock[0])):
                leader.receive_submissions(self.remote.head())
            self.assertEqual(visited[-1],expected)
            self.assertFalse((self.root/'inbox'/expected/'request.json').exists())
        self.engines['leader'].receive_submissions(self.remote.head())
        for identity in identities:self.assertTrue((self.root/'inbox'/identity/'request.json').exists())

    def test_receipt_cache_requires_identical_blobs_and_trust(self):
        from unittest.mock import patch
        p,identity=self.queue();leader=self.engines['leader'];member=self.engines['member']
        member.deliver_outbox(None);leader.receive_submissions(self.remote.head())
        result={'schema_version':1,'id':identity,'state':'accepted','receipt':{'added':1},'error':None}
        write_json(self.root/'inbox'/identity/'result.json',result);leader.receive_submissions(self.remote.head())
        leader.receive_submissions(self.remote.head())
        with patch.object(leader,'verify',wraps=leader.verify) as check:
            leader.receive_submissions(self.remote.head());self.assertEqual(check.call_count,0)
            leader.trusted=dict(leader.trusted,unused=self.keys['member'])
            leader.receive_submissions(self.remote.head());self.assertEqual(check.call_count,2)
        receipt=f'receipts/member/{identity}.json'
        self.remote.update({receipt:b'{"tampered":true}'})
        leader.receive_submissions(self.remote.head())
        self.assertTrue(leader.errors)
        write_json(leader.state/'receive-progress.json',[]) # Corrupt hints do not block revalidation.
        leader.receive_submissions(self.remote.head());self.assertIsInstance(read_json(leader.state/'receive-progress.json'),dict)

    def test_downloads_overlap_but_request_waits_for_all_verified_bytes(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        p,_=self.queue();entry=read_json(p);payload=entry['payload']
        refs={f'results/file-{i}.json':digest(str(i).encode()) for i in range(9)}
        feed={'schema_version':1,'records':[{'provenance':{'producer_session':'member/s-test'},
              'artifacts':{str(i):{'path':name,'sha256':sha} for i,(name,sha) in enumerate(refs.items())}}]}
        data=canonical(feed);self.remote.commits['a'*40].update({name:str(i).encode() for i,name in enumerate(refs)})
        self.remote.commits['a'*40]['results/board-feed.json']=data
        payload.update(feed_sha256=digest(data),artifacts=refs);identity=digest(canonical(payload))
        self.remote.update({f'submissions/member/{identity}.json':canonical(self.engines['member'].sign('submission',payload))},branch='benchmark-submissions/member')
        ready=threading.Event();release=threading.Event();lock=threading.Lock();counts={'active':0,'maximum':0}
        original=self.remote.read
        def slow(commit,path):
            if path in refs:
                with lock:
                    counts['active']+=1;counts['maximum']=max(counts['maximum'],counts['active'])
                    if counts['active']==4:ready.set()
                try:
                    if not release.wait(3):raise RuntimeError('Test transfer gate timed out')
                    return original(commit,path)
                finally:
                    with lock:counts['active']-=1
            return original(commit,path)
        self.remote.read=slow
        with ThreadPoolExecutor(max_workers=1) as caller:
            future=caller.submit(self.engines['leader'].receive_submissions,self.remote.head())
            try:
                self.assertTrue(ready.wait(3));self.assertFalse((self.root/'inbox'/identity/'request.json').exists())
            finally:release.set()
            future.result(timeout=5)
        self.assertEqual(counts['maximum'],4)
        self.assertTrue((self.root/'inbox'/identity/'request.json').exists())
        for name,sha in refs.items():self.assertEqual(digest((self.root/'inbox'/identity/'artifacts'/name).read_bytes()),sha)

    def test_parallel_partial_files_resume_without_redownloading(self):
        import time
        leader=self.engines['leader'];target=self.root/'partial';refs={f'r/{i}':digest(str(i).encode()) for i in range(7)}
        self.remote.commits['b'*40]={p:str(i).encode() for i,p in enumerate(refs)}
        self.remote.fail_path='r/3'
        with self.assertRaises(RemoteError):leader.download_artifacts('b'*40,refs,target,time.monotonic()+5)
        saved={p for p in refs if (target/'artifacts'/p).exists()};self.assertTrue(saved)
        self.remote.fail_path=None;original=self.remote.read;retried=[]
        def record(commit,path):retried.append(path);return original(commit,path)
        self.remote.read=record
        self.assertTrue(leader.download_artifacts('b'*40,refs,target,time.monotonic()+5))
        self.assertFalse(saved.intersection(retried))
        self.assertFalse((target/'request.json').exists())

    def test_backlog_gets_larger_bounded_processing_window(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        leader=self.engines['leader'];clock=[0];identities=[];files={}
        for nonce in range(6):
            payload={'actor':'member','nonce':nonce};identity=digest(canonical(payload));identities.append(identity)
            files[f'submissions/member/{identity}.json']=canonical({'issuer':'member','payload':payload})
        self.remote.update(files,branch='benchmark-submissions/member')
        def verify(envelope,domain,**kwargs):clock[0]+=4;return envelope['payload']
        leader.verify=verify
        with patch('src.benchmark_sync.engine.time',SimpleNamespace(monotonic=lambda:clock[0])):
            leader.receive_submissions(self.remote.head())
        self.assertEqual(leader.receive_status,{'pending':6,'budget_seconds':30})
        for identity in identities:self.assertEqual(read_json(self.root/'inbox'/identity/'result.json')['state'],'rejected')

    def test_member_lane_gets_a_turn_before_leader_backlog_fills_receive_budget(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        leader=self.engines['leader'];files={}
        for actor,count in [('leader',45),('member',1)]:
            for nonce in range(count):
                payload={'schema_version':1,'actor':actor,'nonce':nonce}
                identity=digest(canonical(payload));path=f'submissions/{actor}/{identity}.json'
                files.setdefault(actor,{})[path]=canonical(self.engines[actor].sign('submission',payload))
        self.remote.update(files['leader'],branch='benchmark-submissions/leader')
        self.remote.update(files['member'],branch='benchmark-submissions/member')
        clock=[0];visited=[]
        def verify(envelope,domain,**kwargs):
            if domain=='submission':
                clock[0]+=1;visited.append(envelope['payload']['actor'])
            return envelope['payload']
        leader.verify=verify
        with patch('src.benchmark_sync.engine.time',SimpleNamespace(monotonic=lambda:clock[0])):
            leader.receive_submissions(self.remote.head())
        self.assertEqual(visited[:2],['leader','member'])
        self.assertEqual(leader.receive_status,{'pending':46,'budget_seconds':30})

    def test_sync_in_progress_keeps_real_durable_queue_counts(self):
        self.queue();member=self.engines['member'];observed=[];original=self.remote.head
        def head(branch=None):
            if not observed:observed.append(read_json(member.state/'status.json')['upload'])
            return original(branch)
        self.remote.head=head
        result=member.cycle()
        self.assertEqual(observed,[{'queued':1}])
        self.assertEqual(result['upload'],{'awaiting_receipt':1})

    def test_member_cycle_uses_one_fixed_remote_head_and_reports_stage_timings(self):
        member=self.engines['member'];calls=[];original=self.remote.head
        def head(branch=None):
            calls.append(True)
            status=read_json(member.state/'status.json')
            if len(calls)==1:self.assertEqual(status['current_stage'],'remote_head')
            return original(branch)
        self.remote.head=head
        result=member.cycle()
        self.assertEqual(len(calls),1)
        self.assertEqual(result['state'],'online')
        self.assertIsNone(result['current_stage'])
        self.assertIsNone(result['stage_started_at'])
        self.assertEqual(set(result['stage_timings_ms']),{'remote_head','deliver_outbox'})
        self.assertGreaterEqual(result['cycle_elapsed_ms'],0)
        persisted=read_json(member.state/'status.json')
        self.assertEqual(persisted['stage_timings_ms'],result['stage_timings_ms'])

    def test_accepted_snapshot_cache_rechecks_signed_bytes_without_reunpacking(self):
        from unittest.mock import patch
        import src.benchmark_sync.engine as engine_module
        state=self.engines['member'].state/'accepted'
        db_path=self.root/'ledger.sqlite3'
        with closing(sqlite3.connect(db_path)) as db, db:
            db.executescript('CREATE TABLE records(seq INTEGER,id TEXT,body TEXT); CREATE TABLE events(seq INTEGER,kind TEXT,body TEXT); CREATE TABLE sources(id TEXT,body TEXT);')
        payload=read_central(db_path,frozen_manifest={},algorithms={},code_commit='a'*40)
        manifest=publish_files(payload,state)
        original=engine_module.unpack
        with patch('src.benchmark_sync.engine.unpack',wraps=original) as unpack_mock:
            cached=self.engines['member'].accepted_payload(manifest)
            again=self.engines['member'].accepted_payload(manifest)
            self.assertIs(cached,again)
            self.assertEqual(unpack_mock.call_count,1)
            file=state/manifest['payload_file']
            file.write_bytes(file.read_bytes()+b'x')
            with self.assertRaisesRegex(ValueError,'compressed bytes/hash'):
                self.engines['member'].accepted_payload(manifest)

    def test_signed_delta_arrives_before_full_snapshot_and_full_catches_up(self):
        from unittest.mock import patch
        leader=self.engines['leader'];member=self.engines['member']
        base=snapshot_payload(1);base_manifest=publish_files(base,self.root/'base-published')
        base_object='objects/'+base_manifest['payload_sha256']
        base_channel={'generation':1,'manifest':base_manifest,'object':base_object}
        self.remote.update({base_object:(self.root/'base-published'/base_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',base_channel))})
        member.accept_snapshot(self.remote.head())
        target=snapshot_payload(2);target_manifest=publish_files(target,self.root/'target-published')
        leader.publish_fast_delta(self.remote.head(),base_channel,base,target,target_manifest)
        fast_head=self.remote.head()
        member.accept_snapshot(fast_head)  # The old full channel cannot undo the newer fast target.
        member.accept_fast_snapshot(fast_head)
        current=read_json(member.state/'accepted/current.json')
        self.assertEqual(current['snapshot_id'],target['snapshot_id'])
        self.assertIn('_fast_channel',current)
        self.assertEqual(unpack((member.state/'accepted'/current['payload_file']).read_bytes(),current),target)
        # A second small update can remain cumulative against the same full
        # base while the first large full upload is still pending.
        target=snapshot_payload(3);target_manifest=publish_files(target,self.root/'third-published')
        leader.publish_fast_delta(self.remote.head(),base_channel,base,target,target_manifest)
        member.accept_fast_snapshot(self.remote.head())
        self.assertEqual(read_json(member.state/'accepted/current.json')['record_count'],3)
        target_object='objects/'+target_manifest['payload_sha256']
        full={'generation':2,'manifest':target_manifest,'object':target_object}
        self.remote.update({target_object:(self.root/'third-published'/target_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',full))})
        original_read=self.remote.read
        def no_full_download(commit,path):
            if path==target_object: raise AssertionError('Full snapshot was unnecessarily downloaded')
            return original_read(commit,path)
        with patch.object(self.remote,'read',side_effect=no_full_download):
            member.accept_snapshot(self.remote.head())
        self.assertIn('_channel',read_json(member.state/'accepted/current.json'))

    def test_git_fast_delta_crosses_rest_to_git_and_arrives_before_full(self):
        leader=self.engines['leader'];member=self.engines['member']
        bare=self.root/'fast-remote.git'
        subprocess.run(['git','init','--bare','-q',str(bare)],check=True)
        writer=GitFastLane(self.root/'git-writer','test/repository')
        reader=GitFastLane(self.root/'git-reader','test/repository')
        writer._run(['remote','set-url','origin',str(bare)])
        reader._run(['remote','set-url','origin',str(bare)])
        leader._git_fast_lane=writer;member._git_fast_lane=reader
        member.config['git_fast_enabled']=True
        base=snapshot_payload(1);base_manifest=publish_files(base,self.root/'git-base')
        base_object='objects/'+base_manifest['payload_sha256']
        base_channel={'generation':1,'manifest':base_manifest,'object':base_object}
        self.remote.update({base_object:(self.root/'git-base'/base_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',base_channel))})
        member.accept_snapshot(self.remote.head())
        target=snapshot_payload(2);manifest=publish_files(target,self.root/'git-second')
        leader.publish_fast_delta(self.remote.head(),base_channel,base,target,manifest)
        member.accept_fast_snapshot(self.remote.head())
        self.assertEqual(member.accepted_record_ids(),{r['id'] for r in target['records']})
        third=snapshot_payload(3);third_manifest=publish_files(third,self.root/'git-third')
        leader.publish_git_fast_delta(base_channel,third,third_manifest,pack_delta(base,third))
        status=member.cycle()
        self.assertEqual(status['state'],'online')
        self.assertIn('accept_git_fast_snapshot',status['stage_timings_ms'])
        current=read_json(member.state/'accepted/current.json')
        self.assertEqual(current['snapshot_id'],third['snapshot_id'])
        self.assertEqual(member.accepted_record_ids(),{r['id'] for r in third['records']})
        self.assertEqual(member.verify(current['_fast_channel'],'snapshot-delta',central=True)['transport'],'git')
        fourth=snapshot_payload(4);fourth_manifest=publish_files(fourth,self.root/'rest-fourth')
        leader.publish_fast_delta(self.remote.head(),base_channel,base,fourth,fourth_manifest)
        status=member.cycle()
        self.assertEqual(status['state'],'online')
        self.assertEqual(read_json(member.state/'accepted/current.json')['snapshot_id'],fourth['snapshot_id'])

    def test_git_fast_corruption_falls_back_to_rest_without_accepting_bad_delta(self):
        leader=self.engines['leader'];member=self.engines['member']
        bare=self.root/'corrupt-fast.git'
        subprocess.run(['git','init','--bare','-q',str(bare)],check=True)
        writer=GitFastLane(self.root/'corrupt-writer','test/repository')
        reader=GitFastLane(self.root/'corrupt-reader','test/repository')
        writer._run(['remote','set-url','origin',str(bare)])
        reader._run(['remote','set-url','origin',str(bare)])
        member._git_fast_lane=reader;member.config['git_fast_enabled']=True
        base=snapshot_payload(1);base_manifest=publish_files(base,self.root/'corrupt-base')
        base_object='objects/'+base_manifest['payload_sha256']
        base_channel={'generation':1,'manifest':base_manifest,'object':base_object}
        self.remote.update({base_object:(self.root/'corrupt-base'/base_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',base_channel))})
        member.accept_snapshot(self.remote.head())
        target=snapshot_payload(2);manifest=publish_files(target,self.root/'corrupt-target')
        correct=pack_delta(base,target)
        fast={'schema_version':1,'transport':'git','generation':1,'base_generation':1,
              'base_manifest':base_manifest,'base_object':base_object,'target_manifest':manifest,
              'delta_object':'deltas/'+digest(correct)+'.json.gz','delta_sha256':digest(correct),
              'delta_size':len(correct),'target_canonical_sha256':digest(canonical(target))}
        writer.update({'channels/fast.json':canonical(leader.sign('snapshot-delta',fast)),
                       fast['delta_object']:b'bad bytes'},expected=None)
        leader.publish_fast_delta(self.remote.head(),base_channel,base,target,manifest)
        status=member.cycle()
        self.assertEqual(status['error']['stage'],'git_fast_snapshot')
        self.assertEqual(read_json(member.state/'accepted/current.json')['snapshot_id'],target['snapshot_id'])

    def test_git_fast_offline_member_fetches_missing_base_from_rest(self):
        from unittest.mock import patch
        leader=self.engines['leader'];member=self.engines['member']
        bare=self.root/'recovery-fast.git'
        subprocess.run(['git','init','--bare','-q',str(bare)],check=True)
        writer=GitFastLane(self.root/'recovery-writer','test/repository')
        reader=GitFastLane(self.root/'recovery-reader','test/repository')
        writer._run(['remote','set-url','origin',str(bare)])
        reader._run(['remote','set-url','origin',str(bare)])
        leader._git_fast_lane=writer;member._git_fast_lane=reader
        member.config['git_fast_enabled']=True
        first=snapshot_payload(1);first_manifest=publish_files(first,self.root/'recovery-first')
        first_object='objects/'+first_manifest['payload_sha256']
        self.remote.update({first_object:(self.root/'recovery-first'/first_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',
                                {'generation':1,'manifest':first_manifest,'object':first_object}))})
        member.accept_snapshot(self.remote.head())
        base=snapshot_payload(2);base_manifest=publish_files(base,self.root/'recovery-base')
        base_object='objects/'+base_manifest['payload_sha256']
        base_channel={'generation':2,'manifest':base_manifest,'object':base_object}
        self.remote.update({base_object:(self.root/'recovery-base'/base_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',base_channel))})
        rest_head=self.remote.head()
        target=snapshot_payload(3);target_manifest=publish_files(target,self.root/'recovery-target')
        leader.publish_git_fast_delta(base_channel,target,target_manifest,pack_delta(base,target))
        original_read=self.remote.read
        def read_only_rest_head(commit,path):
            self.assertEqual(commit,rest_head)
            return original_read(commit,path)
        with patch.object(self.remote,'read',side_effect=read_only_rest_head):
            status=member.cycle()
        self.assertEqual(status['state'],'online')
        self.assertEqual(read_json(member.state/'accepted/current.json')['snapshot_id'],target['snapshot_id'])

    def test_fast_snapshot_rejects_tampered_delta_without_changing_current(self):
        leader=self.engines['leader'];member=self.engines['member']
        base=snapshot_payload(1);base_manifest=publish_files(base,self.root/'base-published')
        base_object='objects/'+base_manifest['payload_sha256']
        base_channel={'generation':1,'manifest':base_manifest,'object':base_object}
        self.remote.update({base_object:(self.root/'base-published'/base_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',base_channel))})
        member.accept_snapshot(self.remote.head())
        original=(member.state/'accepted/current.json').read_bytes()
        target=snapshot_payload(2);manifest=publish_files(target,self.root/'target-published')
        leader.publish_fast_delta(self.remote.head(),base_channel,base,target,manifest)
        fast,_=leader.channel(self.remote.head(),'fast','snapshot-delta')
        self.remote.update({fast['delta_object']:b'tampered'})
        with self.assertRaisesRegex(ValueError,'bytes/hash'):
            member.accept_fast_snapshot(self.remote.head())
        self.assertEqual((member.state/'accepted/current.json').read_bytes(),original)
        target_object='objects/'+manifest['payload_sha256']
        self.remote.update({target_object:(self.root/'target-published'/manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',
                                {'generation':2,'manifest':manifest,'object':target_object}))})
        status=member.cycle()
        self.assertEqual(status['error']['stage'],'fast_snapshot')
        self.assertEqual(read_json(member.state/'accepted/current.json')['snapshot_id'],target['snapshot_id'])

    def test_member_cycle_uses_fast_delta_when_full_channel_is_already_new(self):
        from unittest.mock import patch
        leader=self.engines['leader'];member=self.engines['member']
        base=snapshot_payload(1);base_manifest=publish_files(base,self.root/'base-published')
        base_object='objects/'+base_manifest['payload_sha256']
        base_channel={'generation':1,'manifest':base_manifest,'object':base_object}
        self.remote.update({base_object:(self.root/'base-published'/base_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',base_channel))})
        member.accept_snapshot(self.remote.head())
        target=snapshot_payload(2);manifest=publish_files(target,self.root/'target-published')
        leader.publish_fast_delta(self.remote.head(),base_channel,base,target,manifest)
        target_object='objects/'+manifest['payload_sha256']
        self.remote.update({target_object:(self.root/'target-published'/manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',
                                {'generation':2,'manifest':manifest,'object':target_object}))})
        original_read=self.remote.read
        def no_full_download(commit,path):
            if path==target_object: raise AssertionError('Full snapshot download preceded the fast delta')
            return original_read(commit,path)
        with patch.object(self.remote,'read',side_effect=no_full_download):
            status=member.cycle()
        self.assertEqual(status['state'],'online')
        self.assertEqual(read_json(member.state/'accepted/current.json')['snapshot_id'],target['snapshot_id'])
        self.assertIn('_channel',read_json(member.state/'accepted/current.json'))

    def test_fast_delta_accepts_cross_platform_gzip_header_difference(self):
        from unittest.mock import patch
        import gzip
        leader=self.engines['leader'];member=self.engines['member']
        base=snapshot_payload(1);base_manifest=publish_files(base,self.root/'base-published')
        base_object='objects/'+base_manifest['payload_sha256']
        base_channel={'generation':1,'manifest':base_manifest,'object':base_object}
        self.remote.update({base_object:(self.root/'base-published'/base_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',base_channel))})
        member.accept_snapshot(self.remote.head())
        target=snapshot_payload(2);manifest=publish_files(target,self.root/'target-published')
        leader.publish_fast_delta(self.remote.head(),base_channel,base,target,manifest)
        full_object='objects/'+manifest['payload_sha256']
        self.remote.update({full_object:(self.root/'target-published'/manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',
                                {'generation':2,'manifest':manifest,'object':full_object}))})
        original_compress=gzip.compress
        def other_os_header(raw,mtime=0):
            data=original_compress(raw,mtime=mtime)
            return data[:9]+bytes([data[9]^1])+data[10:]
        original_read=self.remote.read
        def no_full_download(commit,path):
            if path==full_object: raise AssertionError('Full snapshot download hid cross-platform delta')
            return original_read(commit,path)
        with patch('src.benchmark_sync.engine.gzip.compress',side_effect=other_os_header), \
             patch.object(self.remote,'read',side_effect=no_full_download):
            status=member.cycle()
        self.assertEqual(status['state'],'online')
        current=read_json(member.state/'accepted/current.json')
        self.assertEqual(current['snapshot_id'],target['snapshot_id'])
        self.assertNotEqual(current['payload_sha256'],manifest['payload_sha256'])
        self.assertIn('_fast_channel',current)
        self.assertEqual(unpack((member.state/'accepted'/current['payload_file']).read_bytes(),current),target)

    def test_fast_snapshot_detects_locally_rewritten_unsigned_status_timestamp(self):
        import gzip
        leader=self.engines['leader'];member=self.engines['member']
        base=snapshot_payload(1);base_manifest=publish_files(base,self.root/'base-published')
        base_object='objects/'+base_manifest['payload_sha256']
        base_channel={'generation':1,'manifest':base_manifest,'object':base_object}
        self.remote.update({base_object:(self.root/'base-published'/base_manifest['payload_file']).read_bytes(),
                            'channels/central.json':canonical(leader.sign('snapshot',base_channel))})
        member.accept_snapshot(self.remote.head())
        target=snapshot_payload(2)
        target['source_status']={'feed':{'checked_at':'2026-09-24T20:00:01+00:00'}}
        target['snapshot_id']=snapshot_id(target)
        manifest=publish_files(target,self.root/'target-published')
        leader.publish_fast_delta(self.remote.head(),base_channel,base,target,manifest)
        member.accept_fast_snapshot(self.remote.head())
        current_path=member.state/'accepted/current.json'
        current=read_json(current_path)
        altered=member.accepted_payload(current).copy()
        altered['source_status']={'feed':{'checked_at':'2026-09-24T20:00:02+00:00'}}
        self.assertEqual(snapshot_id(altered),target['snapshot_id'])
        compressed=gzip.compress(canonical(altered),mtime=0)
        (member.state/'accepted'/current['payload_file']).write_bytes(compressed)
        write_json(current_path,dict(current,payload_sha256=digest(compressed),payload_size=len(compressed)))
        with self.assertRaisesRegex(ValueError,'signed canonical content'):
            member.accept_snapshot(self.remote.head())

    def test_slow_upload_does_not_block_next_signed_snapshot_poll(self):
        from unittest.mock import patch
        member=self.engines['member']
        entered=threading.Event();release=threading.Event()
        heads=[];accepted=[]
        def slow_upload(_known):
            entered.set()
            release.wait(5)
        def next_head():
            value='a'*40 if not heads else 'b'*40
            heads.append(value)
            return value
        try:
            with patch.object(member,'upload_pass',side_effect=slow_upload) as upload, \
                 patch.object(member.remote,'head',side_effect=next_head), \
                 patch.object(member,'accept_snapshot',side_effect=accepted.append):
                first=member.cycle(background_upload=True)
                self.assertTrue(entered.wait(1))
                second=member.cycle(background_upload=True)
                self.assertEqual(accepted,['a'*40,'b'*40])
                self.assertEqual(upload.call_count,1)
                self.assertEqual(first['state'],'online')
                self.assertEqual(second['state'],'online')
        finally:
            release.set()
            if member._upload_thread: member._upload_thread.join(5)

    def test_slow_leader_receive_does_not_block_snapshot_publication(self):
        leader=self.engines['leader'];entered=threading.Event();release=threading.Event()
        heads=[];published=[]
        def slow_receive(head,errors=None):
            entered.set()
            if not release.wait(5):raise RuntimeError('Test receive gate timed out')
        def next_head(branch=None):
            value='a'*40 if not heads else 'b'*40
            heads.append(value);return value
        try:
            from unittest.mock import patch
            with patch.object(leader.remote,'head',side_effect=next_head), \
                 patch.object(leader,'accept_snapshot'), \
                 patch.object(leader,'receive_submissions',side_effect=slow_receive) as receive, \
                 patch.object(leader,'publish_snapshot',side_effect=published.append):
                first=leader.cycle(background_receive=True)
                self.assertTrue(entered.wait(1))
                second=leader.cycle(background_receive=True)
                self.assertEqual(published,['a'*40,'b'*40])
                self.assertEqual(receive.call_count,1)
                self.assertEqual(first['state'],'online')
                self.assertEqual(second['state'],'online')
        finally:
            release.set()
            if leader._receive_thread:leader._receive_thread.join(5)
