import hashlib
import unittest
from src.benchmark_sync.github import GitHub,RemoteError

class RacingGitHub(GitHub):
 def __init__(self,collision):
  self.commits={};self.trees_data={};self.data={};self.latest='a'*40;self.trees={};self.counter=1
  import threading
  self.write_lock=threading.RLock()
  self.branch='test';self.branches={'test':self.latest};self.collision=collision;self.raced=False;self.parents={};self.tree_bodies=[];self.commits[self.latest]={'channel':self.put_blob(b'old')}
 def new(self): self.counter+=1;return f'{self.counter:040x}'
 def head(self,branch=None):return self.branches.get(self.branch if branch is None else branch)
 def tree(self,c):return {p:{'sha':sha,'size':len(self.data[sha])} for p,sha in self.commits[c].items()}
 def tree_entry(self,c,p):
  entry=self.tree(c).get(p)
  if entry is None:raise FileNotFoundError(p)
  return dict(entry,type='blob',mode='100644')
 def blob(self,sha,size=None):return self.data[sha]
 def put_blob(self,data):
  sha=hashlib.sha1(data).hexdigest();self.data[sha]=data;return sha
 def request(self,method,path,body=None):
  if method=='GET':return {'tree':{'sha':path.rsplit('/',1)[-1]}}
  if path=='/git/trees':
   self.tree_bodies.append(body)
   values=dict(self.commits.get(body.get('base_tree'),{}))
   for x in body['tree']:
    sha=x.get('sha') or self.put_blob(x['content'].encode('utf-8'))
    values[x['path']]=sha
   sha=self.new();self.trees_data[sha]=values;return {'sha':sha}
  if path=='/git/commits':
   sha=self.new();self.commits[sha]=self.trees_data[body['tree']];self.parents[sha]=body['parents'];return {'sha':sha}
  if method=='PATCH':
   branch=path.rsplit('/heads/',1)[-1]
   if not self.raced:
    self.raced=True;latest=self.branches[branch];values=dict(self.commits[latest]);values['channel' if self.collision else 'other']=self.put_blob(b'concurrent')
    self.latest=self.new();self.commits[self.latest]=values;self.branches[branch]=self.latest
   if self.parents[body['sha']][0]!=self.branches[branch]:raise RemoteError(422)
   self.latest=body['sha'];self.branches[branch]=body['sha'];return {}
  if method=='POST' and path=='/git/refs':
   branch=body['ref'].removeprefix('refs/heads/')
   if branch in self.branches: raise RemoteError(422)
   self.branches[branch]=body['sha'];self.latest=body['sha'];return {}
  raise AssertionError((method,path))

class GitHubTests(unittest.TestCase):
 def test_cas_updates_resolve_only_touched_paths(self):
  r=RacingGitHub(False);lookups=[]
  def lookup(commit,path):
   lookups.append(path)
   sha=r.commits[commit].get(path)
   if sha is None:raise FileNotFoundError(path)
   return {'sha':sha,'size':len(r.data[sha]),'type':'blob','mode':'100644'}
  r.tree_entry=lookup
  r.tree=lambda commit: (_ for _ in ()).throw(AssertionError('recursive tree must not be read'))
  r.update({'channels/fast.json':b'new'},expected={'channels/fast.json':None})
  self.assertEqual(set(lookups),{'channels/fast.json'})
  self.assertEqual(r.blob(r.commits[r.head()]['channels/fast.json']),b'new')

 def test_same_process_writers_serialize_branch_ref_updates(self):
  import threading
  from concurrent.futures import ThreadPoolExecutor
  r=RacingGitHub(False);barrier=threading.Barrier(3)
  def write(path):
   barrier.wait(timeout=3)
   return r.update({path:path.encode()})
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(write,'submissions/a.json');b=pool.submit(write,'receipts/b.json')
   barrier.wait(timeout=3);a.result(timeout=5);b.result(timeout=5)
  entries=r.tree(r.head())
  self.assertIn('submissions/a.json',entries)
  self.assertIn('receipts/b.json',entries)
  self.assertIn('other',entries)

 def test_actor_submission_lanes_do_not_race_each_other_or_central_ref(self):
  import threading
  from concurrent.futures import ThreadPoolExecutor
  r=RacingGitHub(False);barrier=threading.Barrier(3)
  def write(branch,path):
   barrier.wait(timeout=3)
   return r.update({path:path.encode()},branch=branch)
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(write,'benchmark-submissions/fang','submissions/fang/a.json')
   b=pool.submit(write,'benchmark-submissions/nikola','submissions/nikola/b.json')
   barrier.wait(timeout=3);a.result(timeout=5);b.result(timeout=5)
  central=r.tree(r.head('test'));fang=r.tree(r.head('benchmark-submissions/fang'));nikola=r.tree(r.head('benchmark-submissions/nikola'))
  self.assertIn('channel',central)
  self.assertEqual(set(fang),{'submissions/fang/a.json'})
  self.assertEqual(set(nikola),{'submissions/nikola/b.json'})

 def test_matching_heads_reads_actor_lanes_with_one_prefix_query(self):
  r=RacingGitHub(False);calls=[]
  r.request=lambda method,path: calls.append((method,path)) or [
   {'ref':'refs/heads/benchmark-submissions/fang','object':{'sha':'a'*40}},
   {'ref':'refs/heads/benchmark-submissions/nikola','object':{'sha':'b'*40}},
   {'ref':'refs/heads/benchmark-submissions-other/noise','object':{'sha':'c'*40}}]
  self.assertEqual(r.matching_heads('benchmark-submissions/'),{
   'benchmark-submissions/fang':'a'*40,'benchmark-submissions/nikola':'b'*40})
  self.assertEqual(calls,[('GET','/git/matching-refs/heads/benchmark-submissions/')])

 def test_small_utf8_envelopes_are_inlined_while_binary_snapshots_use_blobs(self):
  r=RacingGitHub(False);binary=b'\x00\xff'+b'x'*70000
  r.update({'submissions/member/one.json':b'{"id":"one"}','objects/snapshot.gz':binary})
  tree=r.tree(r.head());body=r.tree_bodies[-1]
  self.assertEqual(len(body['tree']),2)
  entries={x['path']:x for x in body['tree']}
  self.assertEqual(entries['submissions/member/one.json']['content'],'{"id":"one"}')
  self.assertNotIn('sha',entries['submissions/member/one.json'])
  self.assertIn('sha',entries['objects/snapshot.gz'])
  self.assertNotIn('content',entries['objects/snapshot.gz'])
  self.assertEqual(r.blob(tree['submissions/member/one.json']['sha']),b'{"id":"one"}')
  self.assertEqual(r.blob(tree['objects/snapshot.gz']['sha']),binary)

 def test_head_uses_conditional_etag_and_reuses_cached_sha_on_not_modified(self):
  import json,tempfile,types
  from pathlib import Path
  with tempfile.TemporaryDirectory() as tmp:
   r=GitHub.__new__(GitHub);r.repository='test/repo';r.branch='benchmark-sync-v1';r.cache=Path(tmp)
   calls=[];sha='a'*40
   responses=[{'status':200,'headers':{'ETag':'"stable"'},'data':json.dumps({'object':{'sha':sha}}).encode()},
              {'status':304,'headers':{'ETag':'"stable"'},'data':b''}]
   def request(self,method,path,*,headers=None,response=False):
    calls.append((method,path,headers,response));return responses.pop(0)
   r.request=types.MethodType(request,r)
   self.assertEqual(r.head(),sha);self.assertEqual(r.head(),sha)
   self.assertEqual(calls[1][2],{'If-None-Match':'"stable"'})
   self.assertTrue(calls[1][3])
   cache=list(Path(tmp).glob('head-*.json'))
   self.assertEqual(len(cache),1);self.assertEqual(json.loads(cache[0].read_text())['sha'],sha)

 def test_path_lookup_walks_nonrecursive_trees_and_caches_commit_and_directories(self):
  import threading
  from collections import OrderedDict
  r=GitHub.__new__(GitHub);r.trees=OrderedDict();r.path_trees=OrderedDict();r.commit_tree_roots=OrderedDict();r.tree_lock=threading.Lock()
  commit='a'*40;root='b'*40;folder='c'*40;blob='d'*40;calls=[]
  def request(method,path,**kwargs):
   calls.append(path)
   if path=='/git/commits/'+commit:return {'tree':{'sha':root}}
   if path=='/git/trees/'+root:return {'tree':[{'path':'results','type':'tree','sha':folder}]}
   if path=='/git/trees/'+folder:return {'tree':[{'path':'board-feed.json','type':'blob','mode':'100644','sha':blob,'size':12}]}
   raise AssertionError(path)
  r.request=request
  want={'path':'board-feed.json','type':'blob','mode':'100644','sha':blob,'size':12}
  self.assertEqual(r.tree_entry(commit,'results/board-feed.json'),want)
  self.assertEqual(r.tree_entry(commit,'results/board-feed.json'),want)
  self.assertEqual(calls,['/git/commits/'+commit,'/git/trees/'+root,'/git/trees/'+folder])

 def test_parallel_writers_preserve_unrelated_paths(self):
  r=RacingGitHub(False);r.update({'channel':b'new'},expected={'channel':b'old'})
  self.assertEqual(r.blob(r.tree(r.head())['channel']['sha']),b'new')
  self.assertEqual(r.blob(r.tree(r.head())['other']['sha']),b'concurrent')
 def test_stale_generation_cannot_overwrite_a_new_channel(self):
  r=RacingGitHub(True)
  with self.assertRaisesRegex(RuntimeError,'Channel changed'):r.update({'channel':b'new'},expected={'channel':b'old'})
  self.assertEqual(r.blob(r.tree(r.head())['channel']['sha']),b'concurrent')
 def test_concurrent_rate_limits_keep_longest_durable_cooldown(self):
  import json,tempfile,threading,urllib.error
  from pathlib import Path
  from concurrent.futures import ThreadPoolExecutor
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   r=GitHub.__new__(GitHub);r.repository='test/repo';r.token='test-only'
   r.cooldown_until=0;r.cooldown_lock=threading.Lock();r.cooldown_file=Path(tmp)/'cooldown.json'
   barrier=threading.Barrier(2)
   def limited(request,timeout):
    barrier.wait(timeout=3)
    retry='120' if request.full_url.endswith('/long') else '60'
    raise urllib.error.HTTPError(request.full_url,429,'limited',{'Retry-After':retry},None)
   with patch('src.benchmark_sync.github.urllib.request.urlopen',side_effect=limited),patch('src.benchmark_sync.github.time.time',return_value=100):
    with ThreadPoolExecutor(max_workers=2) as pool:
     jobs=[pool.submit(r.request,'GET','/'+name) for name in ('long','short')]
     for job in jobs:
      with self.assertRaises(RemoteError):job.result(timeout=5)
   self.assertEqual(r.cooldown_until,220)
   self.assertEqual(json.loads(r.cooldown_file.read_text())['until'],220)
 def test_only_safe_get_disconnects_retry_and_tls_verification_stays_strict(self):
  import io,json,ssl,urllib.error
  from unittest.mock import patch
  r=GitHub.__new__(GitHub);r.repository='test/repo';r.token='test-only';r.cooldown_until=0
  eof=urllib.error.URLError(ssl.SSLEOFError('test EOF'))
  with patch('src.benchmark_sync.github.urllib.request.urlopen',side_effect=[eof,eof,io.BytesIO(b'{"ok":true}')]) as call,patch('src.benchmark_sync.github.time.sleep'):
   self.assertEqual(r.request('GET','/test'),{'ok':True});self.assertEqual(call.call_count,3)
  for method,error in [('POST',eof),('PATCH',eof),('GET',urllib.error.URLError(ssl.SSLCertVerificationError('test certificate'))),('GET',urllib.error.URLError(TimeoutError('test timeout')))]:
   with self.subTest(method=method,error=error),patch('src.benchmark_sync.github.urllib.request.urlopen',side_effect=error) as call,patch('src.benchmark_sync.github.time.sleep'):
    with self.assertRaises(urllib.error.URLError):r.request(method,'/test',{} if method!='GET' else None)
    self.assertEqual(call.call_count,1)
 def test_fixed_source_tree_survives_publications_with_bounded_cache(self):
  from collections import OrderedDict
  import threading,types
  r=RacingGitHub(False);r.trees=OrderedDict();r.tree_lock=threading.Lock()
  r.tree=types.MethodType(GitHub.tree,r);original=r.request;calls=[]
  def request(method,path,body=None,params=None):
   if method=='GET':calls.append(path)
   if method=='GET' and path.startswith('/git/trees/'):
    commit=path.rsplit('/',1)[-1]
    return {'tree':[{'path':p,'type':'blob','sha':sha,'mode':'100644','size':len(r.data[sha])} for p,sha in r.commits[commit].items()]}
   return original(method,path,body)
  r.request=request;source='b'*40;r.commits[source]={'source.json':r.put_blob(b'source')}
  before=r.tree(source);source_calls=lambda:sum(p.endswith('/'+source) for p in calls)
  self.assertEqual(source_calls(),2)
  r.update({'channel':b'new'},expected={'channel':b'old'})
  self.assertIs(r.tree(source),before);self.assertEqual(source_calls(),2)
  for i in range(20):
   commit=f'{i+100:040x}';r.commits[commit]={};r.tree(commit)
  self.assertEqual(len(r.trees),16)
  r.tree(source);self.assertEqual(source_calls(),4)
 def test_existing_local_git_objects_avoid_network_without_reading_worktree(self):
  import tempfile,subprocess
  from pathlib import Path
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);repo=root/'repo';repo.mkdir()
   subprocess.run(['git','init','-q',str(repo)],check=True)
   raw=b'committed artifact bytes'
   sha=subprocess.check_output(['git','-C',str(repo),'hash-object','-w','--stdin'],input=raw).decode().strip()
   (repo/'artifact.json').write_bytes(b'changed uncommitted bytes')
   r=GitHub.__new__(GitHub);r.local_repository=repo;r.cache=root/'cache';r.cache.mkdir();calls=[]
   def network(*a,**k):calls.append(a);return b'fallback bytes'
   r.request=network
   self.assertEqual(r.blob(sha,len(raw)),raw);self.assertEqual(calls,[])
   missing=hashlib.sha1(b'blob 14\0fallback bytes').hexdigest()
   self.assertEqual(r.blob(missing,14),b'fallback bytes');self.assertEqual(len(calls),1)
   self.assertEqual((repo/'artifact.json').read_bytes(),b'changed uncommitted bytes')
