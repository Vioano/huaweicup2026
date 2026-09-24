"""Own website/worker child processes; verify candidates, retain last-good releases."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from .engine import read_json, write_json
from .snapshot import now, digest
from .locking import exclusive_lock


def free_port():
    with socket.socket() as s: s.bind(('127.0.0.1',0));return s.getsockname()[1]


def get(url):
    with urllib.request.urlopen(url,timeout=3) as r:
        data=r.read(32*1024*1024+1)
    if len(data)>32*1024*1024: raise ValueError('Oversized health response')
    return data


def check_health(proc,port,release,timeout=20):
    deadline=time.monotonic()+timeout;manifest=read_json(Path(release['path'])/'release.json')
    last='no response'
    while time.monotonic()<deadline:
        if proc.poll() is not None: raise RuntimeError('Website exited during health check')
        try:
            health=json.loads(get(f'http://127.0.0.1:{port}/api/v1/health'))
            if health.get('status') not in ('ok','degraded'): raise ValueError('Website is not healthy')
            for endpoint,name in (('/app.js','app.js'),('/style.css','style.css')):
                sha=manifest['files']['src/benchmark_board/web/'+name]['sha256']
                if digest(get(f'http://127.0.0.1:{port}'+endpoint))!=sha: raise ValueError('Served UI bytes differ from release')
            html=get(f'http://127.0.0.1:{port}/')
            expected=manifest['files']['src/benchmark_board/web/index.html']['sha256']
            if digest(html)!=expected:
                runtime=json.loads(get(f'http://127.0.0.1:{port}/api/v1/runtime'))
                files={name:manifest['files']['src/benchmark_board/web/'+name]['sha256'] for name in ('index.html','app.js','style.css')}
                from .snapshot import canonical
                if runtime.get('ui_asset_id')!=digest(canonical(files)) or runtime.get('file_hashes')!=files or runtime.get('served_html_sha256')!=digest(html):
                    raise ValueError('Served HTML/runtime fingerprint differs from release')
            return health
        except Exception as error: last=str(error);time.sleep(.25)
    raise RuntimeError('Website health check failed: '+last)


def stop(proc):
    if proc is None or proc.poll() is not None: return
    proc.terminate()
    try: proc.wait(timeout=8)
    except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=5)


class Supervisor:
    def __init__(self,config_path):
        self.config_path=Path(config_path).resolve();self.config=read_json(config_path)
        self.state=Path(self.config['state']);self.software=self.state/'software'
        self.board=None;self.worker=None;self.stopping=False
        self.logdir=self.state/'logs';self.logdir.mkdir(parents=True,exist_ok=True)
        self.children=[]
    def spawn(self,command,cwd,logname):
        with (self.logdir/logname).open('ab') as log:
            proc=subprocess.Popen(command,cwd=str(cwd),stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        self.children.append(proc);return proc
    def board_start(self,release,port,probe=False):
        root=Path(release['path'])
        state=self.state/'probe-board' if probe else (Path(self.config['central']['ledger']) if self.config['role']=='leader' else self.state/'member-board')
        cmd=[self.config.get('python',sys.executable),'-X','utf8','-u',str(root/'src/benchmark_board/app.py'),
             '--state',str(state)]
        if not probe and self.config['role']=='leader': cmd+=['--repo',self.config['central']['repo']]
        cmd+=['serve','--port',str(port),'--sync-status',str(self.state/'status.json')]
        if probe or self.config['role']=='member': cmd+=['--mirror',str(self.state/'accepted/current.json'),'--no-sync']
        else: cmd+=['--sync-inbox',self.config['central']['inbox']]
        return self.spawn(cmd,root,'website-probe.log' if probe else 'website.log')
    def worker_start(self,release):
        return self.spawn([self.config.get('python',sys.executable),'-X','utf8','-u','-m','src.benchmark_sync',
                           '--config',str(self.config_path),'run'],release['path'],'sync.log')
    def record(self,release,health,error=None):
        write_json(self.software/'status.json',{'release_id':release['release_id'],'code_commit':release['code_commit'],
                   'installed_at':now(),'health':health,'error':error})
    def activate(self,desired,old):
        port=self.config.get('port',52341)
        probe=None
        try:
            probe_port=free_port();probe=self.board_start(desired,probe_port,True)
            check_health(probe,probe_port,desired)
        finally: stop(probe)
        # Only terminate children this supervisor owns, never an arbitrary port owner.
        stop(self.board);self.board=None
        try:
            self.board=self.board_start(desired,port)
            check_health(self.board,port,desired)
        except Exception as error:
            stop(self.board);self.board=None
            if old:
                self.board=self.board_start(old,port);check_health(self.board,port,old)
                self.record(old,'rollback',str(error))
            raise
        stop(self.worker);self.worker=None
        if old: write_json(self.software/'previous.json',old)
        write_json(self.software/'active.json',desired)
        self.record(desired,'ok')
        self.worker=self.worker_start(desired)
        return desired
    def run(self,bootstrap):
        port=self.config.get('port',52341)
        with socket.socket() as probe:
            try: probe.bind(('127.0.0.1',port))
            except OSError: raise RuntimeError(f'Port {port} already in use. One-time controlled handoff required; no process was killed.') from None
        active_path=self.software/'active.json'
        active=read_json(active_path) if active_path.exists() else None
        rejected=read_json(self.software/'rejected.json') if (self.software/'rejected.json').exists() else {}
        self.worker=self.worker_start(active or bootstrap)
        last_restart=0
        try:
            while not self.stopping:
                desired_path=self.software/'desired.json'
                desired=read_json(desired_path) if desired_path.exists() else active
                if desired and (self.state/'accepted/current.json').exists():
                    if (not active or desired['release_id']!=active['release_id']) and desired['release_id'] not in rejected:
                        try: active=self.activate(desired,active)
                        except Exception as error:
                            rejected[desired['release_id']]={'at':now(),'error':str(error)};write_json(self.software/'rejected.json',rejected)
                    elif active and (self.board is None or self.board.poll() is not None) and time.monotonic()-last_restart>10:
                        last_restart=time.monotonic()
                        try:
                            self.board=self.board_start(active,port);check_health(self.board,port,active)
                        except Exception as error: stop(self.board);self.record(active,'error',str(error))
                if self.worker is None or self.worker.poll() is not None:
                    time.sleep(3);self.worker=self.worker_start(active or bootstrap)
                time.sleep(1)
        finally:
            for proc in self.children: stop(proc)
            for proc in self.children:
                if proc.poll() is not None: proc.wait()


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--bootstrap',type=Path,required=True)
    args=p.parse_args();s=Supervisor(args.config)
    def end(*_): s.stopping=True
    signal.signal(signal.SIGTERM,end);signal.signal(signal.SIGINT,end)
    with exclusive_lock(s.state/'supervisor.lock'): s.run(read_json(args.bootstrap))

if __name__=='__main__': main()
