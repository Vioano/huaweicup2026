import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from src.benchmark_sync.engine import read_json,write_json
from src.benchmark_sync.install import launcher
from src.benchmark_sync.snapshot import digest
from src.benchmark_sync.supervisor import free_port,get
from tests.benchmark_sync.test_supervisor import APP


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.state=self.root/'state';self.state.mkdir();self.port=free_port();self.proc=None
        self.software=self.state/'software';self.software.mkdir()
        write_json(self.state/'config.json',{'state':str(self.state),'python':sys.executable,'role':'member','port':self.port})
        write_json(self.state/'accepted/current.json',{})
        launcher(self.state)

    def tearDown(self):
        if self.proc and self.proc.poll() is None:
            report=read_json(self.software/'launcher.json')
            write_json(self.software/'supervisor-stop.json',{'pid':report['supervisor_pid']})
            try:self.proc.wait(timeout=35)
            except subprocess.TimeoutExpired:self.proc.terminate();self.proc.wait(timeout=35)
        if hasattr(self,'log'):self.log.close()
        self.temporary.cleanup()

    def release(self,name,failure=''):
        root=self.root/name;source=Path(__file__).resolve().parents[2]/'src/benchmark_sync'
        shutil.copytree(source,root/'src/benchmark_sync',ignore=shutil.ignore_patterns('__pycache__'))
        # Offline process fixture: real supervisor and launcher; no Git/network or ledger writes.
        (root/'src/benchmark_sync/__main__.py').write_text('import time\nwhile True: time.sleep(1)\n')
        web=root/'src/benchmark_board/web';web.mkdir(parents=True)
        for filename in ('index.html','app.js','style.css'):(web/filename).write_text(name+filename)
        (web.parent/'app.py').write_text(APP.format(failure=failure))
        release={'release_id':name,'code_commit':name[0]*40,'path':str(root)}
        files={p.relative_to(root).as_posix():{'sha256':digest(p.read_bytes())} for p in web.iterdir()}
        write_json(root/'release.json',dict(release,files=files))
        return release

    def start(self,release):
        write_json(self.state/'bootstrap.json',release);write_json(self.software/'active.json',release)
        write_json(self.software/'desired.json',release)
        self.log=(self.state/'test.log').open('ab')
        self.proc=subprocess.Popen([sys.executable,'-X','utf8',str(self.state/'start.py')],stdout=self.log,stderr=subprocess.STDOUT)

    def wait(self,predicate,timeout=35):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if self.proc.poll() is not None:self.fail((self.state/'test.log').read_text())
            try:
                result=predicate()
                if result:return result
            except (OSError,ValueError,KeyError):pass
            time.sleep(.1)
        self.fail('No expected state; log: '+(self.state/'test.log').read_text())

    def ready(self,name):
        def check():
            report=read_json(self.software/'supervisor.json')
            return report if report['release_id']==name and report['state']=='ready' else None
        return self.wait(check)

    def test_same_native_parent_hands_off_actual_supervisor_and_rejects_second_launcher(self):
        one=self.release('aaaa');two=self.release('bbbb');self.start(one)
        before=self.ready('aaaa');parent=self.proc.pid
        other=subprocess.run([sys.executable,str(self.state/'start.py')],capture_output=True,timeout=10)
        self.assertNotEqual(other.returncode,0)
        write_json(self.software/'desired.json',two)
        after=self.ready('bbbb')
        self.assertEqual(self.proc.pid,parent)
        self.assertNotEqual(before['pid'],after['pid'])
        self.assertNotEqual(before['board_pid'],after['board_pid'])
        self.assertEqual(Path(after['path']).resolve(),Path(two['path']).resolve());self.assertEqual(after['code_commit'],'b'*40)
        self.assertEqual(after['launcher_protocol'],1)
        self.assertEqual(get(f'http://127.0.0.1:{self.port}/'),b'bbbbindex.html')

    def test_candidate_supervisor_import_failure_keeps_existing_children(self):
        one=self.release('aaaa');bad=self.release('bbbb');self.start(one);before=self.ready('aaaa')
        (Path(bad['path'])/'src/benchmark_sync/supervisor.py').write_text('raise RuntimeError("broken supervisor")\n')
        write_json(self.software/'desired.json',bad)
        self.wait(lambda:read_json(self.software/'rejected.json').get('bbbb'))
        self.assertEqual(read_json(self.software/'active.json')['release_id'],'aaaa')
        self.assertEqual(read_json(self.software/'supervisor.json')['pid'],before['pid'])
        self.assertEqual(get(f'http://127.0.0.1:{self.port}/'),b'aaaaindex.html')

    def test_new_supervisor_startup_failure_restores_previous_without_ledger_change(self):
        one=self.release('aaaa');bad=self.release('bbbb');self.start(one);before=self.ready('aaaa')
        path=Path(bad['path'])/'src/benchmark_sync/supervisor.py'
        original=path.read_text();path.write_text('import sys\nif "--check" not in sys.argv: raise SystemExit(9)\n'+original.replace('from __future__ import annotations',''))
        sentinel=self.state/'ledger-preserved';sentinel.write_bytes(b'unchanged')
        write_json(self.software/'desired.json',bad)
        self.wait(lambda:read_json(self.software/'rejected.json').get('bbbb'))
        self.wait(lambda:read_json(self.software/'supervisor.json').get('pid')!=before['pid'] and read_json(self.software/'supervisor.json').get('state')=='ready')
        self.assertEqual(read_json(self.software/'active.json')['release_id'],'aaaa')
        self.assertEqual(sentinel.read_bytes(),b'unchanged')
        self.assertEqual(get(f'http://127.0.0.1:{self.port}/'),b'aaaaindex.html')
