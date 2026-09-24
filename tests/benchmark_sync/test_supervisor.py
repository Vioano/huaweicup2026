from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch
from src.benchmark_sync.supervisor import check_health
from src.benchmark_sync.snapshot import canonical
from src.benchmark_sync.supervisor import Supervisor, stop, free_port, get
from src.benchmark_sync.engine import write_json,read_json
from src.benchmark_sync.snapshot import digest

APP='''import argparse,json\nfrom pathlib import Path\nfrom http.server import BaseHTTPRequestHandler,HTTPServer\np=argparse.ArgumentParser();p.add_argument('--state');a,_=p.parse_known_args();root=Path(__file__).parent\n{failure}\nclass H(BaseHTTPRequestHandler):\n def log_message(self,*a): pass\n def do_GET(self):\n  data=b'{{"status":"ok"}}' if self.path=='/api/v1/health' else (root/'web'/{{'/':'index.html','/app.js':'app.js','/style.css':'style.css'}}[self.path]).read_bytes()\n  self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)\nimport sys\nHTTPServer(('127.0.0.1',int(sys.argv[sys.argv.index('--port')+1])),H).serve_forever()\n'''

class SupervisorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.port=free_port()
  self.config=self.root/'config.json';write_json(self.config,{'state':str(self.root/'state'),'python':sys.executable,'role':'member','port':self.port})
  self.s=Supervisor(self.config);self.s.worker_start=lambda r:None
 def tearDown(self):
  for p in self.s.children: stop(p)
  self.tmp.cleanup()
 def release(self,name,failure=''):
  root=self.root/name;web=root/'src/benchmark_board/web';web.mkdir(parents=True)
  for filename in ('index.html','app.js','style.css'): (web/filename).write_text(name+filename)
  (web.parent/'app.py').write_text(APP.format(failure=failure))
  files={p.relative_to(root).as_posix():{'sha256':digest(p.read_bytes())} for p in web.iterdir()}
  write_json(root/'release.json',{'files':files})
  return {'release_id':name,'code_commit':'a'*40,'path':str(root)}
 def test_candidate_failure_keeps_existing_server(self):
  old=self.release('one');self.s.activate(old,None);pid=self.s.board.pid
  bad=self.release('two','raise SystemExit(9)')
  with self.assertRaises(RuntimeError):self.s.activate(bad,old)
  self.assertEqual(self.s.board.pid,pid);self.assertEqual(get(f'http://127.0.0.1:{self.port}/'),'oneindex.html'.encode())
 def test_server_cannot_attest_to_its_own_modified_html(self):
  r=self.release('one');root=Path(r['path']);index=root/'src/benchmark_board/web/index.html'
  index.write_text('<html><head></head><body>trusted</body></html>')
  manifest=read_json(root/'release.json');manifest['files']['src/benchmark_board/web/index.html']['sha256']=digest(index.read_bytes());write_json(root/'release.json',manifest)
  hashes={n:manifest['files']['src/benchmark_board/web/'+n]['sha256'] for n in ('index.html','app.js','style.css')}
  identity=digest(canonical(hashes));altered=index.read_bytes().replace(b'trusted',b'changed')
  responses={'/api/v1/health':b'{"status":"ok"}','/':altered,
             '/app.js':(root/'src/benchmark_board/web/app.js').read_bytes(),'/style.css':(root/'src/benchmark_board/web/style.css').read_bytes(),
             '/api/v1/runtime':canonical({'ui_asset_id':identity,'file_hashes':hashes,'served_html_sha256':digest(altered)})}
  class Live:
   def poll(self):return None
  with patch('src.benchmark_sync.supervisor.get',side_effect=lambda u:responses['/'+u.split('/',3)[3]]):
   with self.assertRaisesRegex(RuntimeError,'trusted deterministic'):check_health(Live(),1,r,timeout=.1)

 def test_failure_on_actual_port_restores_previous_release(self):
  old=self.release('one');self.s.activate(old,None)
  bad=self.release('two',"if Path(a.state).name!='probe-board': raise SystemExit(9)")
  with self.assertRaises(RuntimeError):self.s.activate(bad,old)
  self.assertEqual(get(f'http://127.0.0.1:{self.port}/'),'oneindex.html'.encode())
  self.assertEqual(read_json(self.s.software/'active.json')['release_id'],'one')
  self.assertEqual(read_json(self.s.software/'status.json')['health'],'rollback')
