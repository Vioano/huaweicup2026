from pathlib import Path
import tempfile
import unittest
import sys
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
  files={str(p.relative_to(root)):{'sha256':digest(p.read_bytes())} for p in web.iterdir()}
  write_json(root/'release.json',{'files':files})
  return {'release_id':name,'code_commit':'a'*40,'path':str(root)}
 def test_candidate_failure_keeps_existing_server(self):
  old=self.release('one');self.s.activate(old,None);pid=self.s.board.pid
  bad=self.release('two','raise SystemExit(9)')
  with self.assertRaises(RuntimeError):self.s.activate(bad,old)
  self.assertEqual(self.s.board.pid,pid);self.assertEqual(get(f'http://127.0.0.1:{self.port}/'),'oneindex.html'.encode())
 def test_failure_on_actual_port_restores_previous_release(self):
  old=self.release('one');self.s.activate(old,None)
  bad=self.release('two',"if Path(a.state).name!='probe-board': raise SystemExit(9)")
  with self.assertRaises(RuntimeError):self.s.activate(bad,old)
  self.assertEqual(get(f'http://127.0.0.1:{self.port}/'),'oneindex.html'.encode())
  self.assertEqual(read_json(self.s.software/'active.json')['release_id'],'one')
  self.assertEqual(read_json(self.s.software/'status.json')['health'],'rollback')
