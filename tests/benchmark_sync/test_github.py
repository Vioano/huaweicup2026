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
