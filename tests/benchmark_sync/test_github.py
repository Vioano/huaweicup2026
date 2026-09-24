import hashlib
import unittest
from src.benchmark_sync.github import GitHub,RemoteError

class RacingGitHub(GitHub):
 def __init__(self,collision):
  self.commits={};self.trees_data={};self.data={};self.latest='a'*40;self.trees={};self.counter=1
  self.branch='test';self.collision=collision;self.raced=False;self.parents={};self.commits[self.latest]={'channel':self.put_blob(b'old')}
 def new(self): self.counter+=1;return f'{self.counter:040x}'
 def head(self):return self.latest
 def tree(self,c):return {p:{'sha':sha,'size':len(self.data[sha])} for p,sha in self.commits[c].items()}
 def blob(self,sha,size=None):return self.data[sha]
 def put_blob(self,data):
  sha=hashlib.sha1(data).hexdigest();self.data[sha]=data;return sha
 def request(self,method,path,body=None):
  if method=='GET':return {'tree':{'sha':path.rsplit('/',1)[-1]}}
  if path=='/git/trees':
   values=dict(self.commits.get(body.get('base_tree'),{}));values.update({x['path']:x['sha'] for x in body['tree']})
   sha=self.new();self.trees_data[sha]=values;return {'sha':sha}
  if path=='/git/commits':
   sha=self.new();self.commits[sha]=self.trees_data[body['tree']];self.parents[sha]=body['parents'];return {'sha':sha}
  if method=='PATCH':
   if not self.raced:
    self.raced=True;values=dict(self.commits[self.latest]);values['channel' if self.collision else 'other']=self.put_blob(b'concurrent')
    self.latest=self.new();self.commits[self.latest]=values
   if self.parents[body['sha']][0]!=self.latest:raise RemoteError(422)
   self.latest=body['sha'];return {}
  raise AssertionError((method,path))

class GitHubTests(unittest.TestCase):
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
