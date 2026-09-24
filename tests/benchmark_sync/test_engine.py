from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from src.benchmark_sync.engine import Engine, write_json, read_json
from src.benchmark_sync.snapshot import canonical, digest
from src.benchmark_sync.signing import Signatures
from src.benchmark_sync.github import RemoteError

class Remote:
    repository='test/repository'
    def __init__(self): self.commits={};self.current=None;self.fail_path=None
    def head(self): return self.current
    def tree(self,commit): return {p:{} for p in self.commits[commit]}
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

    def test_untrusted_submitter_never_reaches_ledger(self):
        p,identity=self.queue();self.engines['member'].deliver_outbox(None)
        self.engines['leader'].trusted={'leader':self.keys['leader']}
        self.engines['leader'].receive_submissions(self.remote.head())
        self.assertFalse((self.root/'inbox'/identity/'request.json').exists())
