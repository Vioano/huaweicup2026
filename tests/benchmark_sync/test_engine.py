from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from src.benchmark_sync.engine import Engine, write_json, read_json
from src.benchmark_sync.snapshot import canonical, digest, publish_files, read_central, snapshot_id
from src.benchmark_sync.signing import Signatures
from src.benchmark_sync.github import RemoteError

class Remote:
    repository='test/repository'
    def __init__(self): self.commits={};self.current=None;self.fail_path=None
    def head(self): return self.current
    def tree(self,commit): return {p:{'sha':hashlib.sha1(b'blob '+str(len(v)).encode()+b'\0'+v).hexdigest()} for p,v in self.commits[commit].items()}
    def read(self,commit,path):
        if path==self.fail_path: raise RemoteError(503)
        if path not in self.commits[commit]: raise FileNotFoundError(path)
        return self.commits[commit][path]
    def update(self,files,parents=(),expected=None):
        values=dict(self.commits.get(self.current,{}));values.update(files)
        self.current=hashlib.sha1(canonical({p:digest(v) for p,v in values.items()})).hexdigest()
        self.commits[self.current]=values;return self.current
    def request(self,method,path):
        if path.rsplit('/',1)[-1] not in self.commits: raise RemoteError(404)
        return {}

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.remote=Remote();self.sign=Signatures()
        self.keys={a:self.sign.generate(self.root/(a+'.pem')) for a in ('leader','member')}
        self.configs={a:{'state':str(self.root/a),'actor':a,'leader':'leader','role':a if a=='leader' else 'member',
                     'trusted_keys':self.keys,'private_key':str(self.root/(a+'.pem'))} for a in self.keys}
        self.engines={a:Engine(c,self.remote,self.sign) for a,c in self.configs.items()}
        self.engines['leader'].config['central']={'inbox':str(self.root/'inbox')}
    def tearDown(self): self.tmp.cleanup()
    def test_unchanged_snapshot_rechecks_signed_bytes_without_decoding(self):
        db_path=self.root/'ledger.sqlite3'
        with closing(sqlite3.connect(db_path)) as db, db:
            db.executescript('CREATE TABLE records(seq INTEGER,id TEXT,body TEXT); '
                             'CREATE TABLE events(seq INTEGER,kind TEXT,body TEXT); '
                             'CREATE TABLE sources(id TEXT,body TEXT);')
            record={'id':'1'*64,'attempt_id':'attempt-1','revision':1,'problem':'P1',
                    'case_id':'001','cores':1,'metrics':{'makespan_cycles':1},'eligible':True}
            db.execute('INSERT INTO records VALUES(?,?,?)',(1,record['id'],json.dumps(record)))
            db.execute('INSERT INTO events VALUES(?,?,?)',(1,'record',json.dumps({'id':record['id']})))
        payload=read_central(db_path,frozen_manifest={},algorithms={},code_commit='a'*40)
        payload['publisher']['actor']='leader'
        payload['snapshot_id']=snapshot_id(payload)
        published=self.root/'published'
        manifest={k:v for k,v in publish_files(payload,published).items() if k!='unchanged'}
        channel={'generation':1,'manifest':manifest,'object':'objects/'+manifest['payload_sha256']}
        envelope=self.engines['leader'].sign('snapshot',channel)
        head=self.remote.update({'channels/central.json':canonical(envelope),
                                 channel['object']:(published/manifest['payload_file']).read_bytes()})
        member=self.engines['member']
        member.accept_snapshot(head)
        current=self.root/'member'/'accepted'/'current.json'
        accepted=self.root/'member'/'accepted'/manifest['payload_file']
        self.assertEqual(read_json(current)['snapshot_id'],manifest['snapshot_id'])
        with patch('src.benchmark_sync.engine.unpack',side_effect=AssertionError('redecoded')):
            member.accept_snapshot(head)
            accepted.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'compressed bytes/hash mismatch'):
                member.accept_snapshot(head)
        self.assertEqual(read_json(current)['snapshot_id'],manifest['snapshot_id'])
    def queue(self,actor='member'):
        artifact=b'{"test":true}';feed={'schema_version':1,'records':[{'provenance':{'producer_session':actor+'/s-test'},'artifacts':{'plan':{'path':'results/plan.json','sha256':digest(artifact)}}}]}
        feed_bytes=canonical(feed);commit='a'*40
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
    def test_leader_can_also_submit_and_neighbour_corruption_is_isolated(self):
        p,identity=self.queue('leader');bad=self.root/'leader'/'outbox'/'broken'/'entry.json';bad.parent.mkdir(parents=True);bad.write_text('{')
        leader=self.engines['leader'];leader.deliver_outbox(None)
        self.assertEqual(read_json(p)['state'],'awaiting_receipt');self.assertTrue((self.root/'leader'/'quarantine'/'broken').exists())
        leader.receive_submissions(self.remote.head());self.assertTrue((self.root/'inbox'/identity/'request.json').exists())
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
                self.remote.update({path:canonical(self.engines['member'].sign('submission',payload))})
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
        for _,identity,_ in items[:-1]:
            files[f'receipts/member/{identity}.json']=canonical({'payload':{'id':identity,'actor':'member','state':'accepted'}})
        self.remote.update(files)
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

    def test_partial_batch_yields_to_next_pending_after_restart(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        p,identity=self.queue();self.engines['member'].deliver_outbox(None)
        payload=read_json(p)['payload'];other=dict(payload,nonce='second')
        other_id=digest(canonical(other))
        self.remote.update({f'submissions/member/{other_id}.json':canonical(self.engines['member'].sign('submission',other))})
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
        self.remote.update({f'submissions/member/{identity}.json':canonical(self.engines['member'].sign('submission',payload))})
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
        self.remote.update(files)
        def verify(envelope,domain,**kwargs):clock[0]+=4;return envelope['payload']
        leader.verify=verify
        with patch('src.benchmark_sync.engine.time',SimpleNamespace(monotonic=lambda:clock[0])):
            leader.receive_submissions(self.remote.head())
        self.assertEqual(leader.receive_status,{'pending':6,'budget_seconds':30})
        for identity in identities:self.assertEqual(read_json(self.root/'inbox'/identity/'result.json')['state'],'rejected')

    def test_sync_in_progress_keeps_real_durable_queue_counts(self):
        self.queue();member=self.engines['member'];observed=[];original=self.remote.head
        def head():
            if not observed:observed.append(read_json(member.state/'status.json')['upload'])
            return original()
        self.remote.head=head
        result=member.cycle()
        self.assertEqual(observed,[{'queued':1}])
        self.assertEqual(result['upload'],{'awaiting_receipt':1})
