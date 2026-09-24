from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import subprocess
import time
from .engine import Engine, read_json, write_json
from .github import GitHub
from .locking import exclusive_lock
from .signing import Signatures
from .submission import enqueue
from .release import publish_release, receive_release


def poll_delay(config,status,failures,cooldown_until):
    delay=min(300,config.get('poll_seconds',2)*2**min(failures,5))
    if config['role']=='leader' and status['state']=='online' and status.get('receive',{}).get('pending',0):
        delay=min(delay,2)
    return max(delay,cooldown_until-time.time(),status.get('error',{}).get('retry_after',0) if status.get('error') else 0)

def runtime_stage(state,status,name,operation):
    started=time.monotonic();timings=status.setdefault('runtime_stage_timings_ms',{})
    status['runtime_stage']=name;status['runtime_stage_started_at']=datetime.now(timezone.utc).isoformat()
    write_json(state/'status.json',status)
    try: return operation()
    finally:
        timings[name]=round((time.monotonic()-started)*1000,1)
        status['runtime_stage']=None;status['runtime_stage_started_at']=None
        write_json(state/'status.json',status)


def main():
    p=argparse.ArgumentParser(description='Model-free benchmark synchronization')
    p.add_argument('--config',type=Path)
    sub=p.add_subparsers(dest='command',required=True)
    key=sub.add_parser('keygen');key.add_argument('--private-key',type=Path,required=True)
    q=sub.add_parser('enqueue');q.add_argument('--repo',type=Path,required=True);q.add_argument('--commit',required=True);q.add_argument('--feed',required=True)
    sub.add_parser('once');sub.add_parser('run')
    release=sub.add_parser('publish-release');release.add_argument('--repo',type=Path,required=True);release.add_argument('--commit',required=True)
    args=p.parse_args()
    if args.command=='keygen':
        s=Signatures();print(json.dumps({'public_key':s.generate(args.private_key)},ensure_ascii=False));return
    if not args.config: p.error('--config is required')
    config=read_json(args.config)
    if config['role'] not in ('leader','member') or not 2<=config.get('poll_seconds',2)<=3600: raise ValueError('Invalid runtime role/poll interval')
    # Keep older installations on the low-latency default without editing their
    # private config file; respect the two-second polling floor.
    config['poll_seconds']=min(config.get('poll_seconds',2),2)
    state=Path(config['state']);state.mkdir(parents=True,exist_ok=True)
    if args.command=='enqueue':
        print(enqueue(state,args.repo,args.commit,args.feed,config['actor']));return
    with exclusive_lock(state/'runtime.lock'):
        s=Signatures(config.get('node'))
        remote=GitHub(config['repository'],config.get('branch','benchmark-sync-v1'),state/'git-cache',actor=config['actor'],gh=config.get('gh','gh'),
                      local_repository=config.get('central',{}).get('repo') if config['role']=='leader' else None)
        e=Engine(config,remote,s)
        if args.command=='publish-release':
            if config['role']!='leader': raise ValueError('Only central publisher may release code')
            print(json.dumps(publish_release(e,args.repo,args.commit),ensure_ascii=False));return
        failures=0;last_release_check=0;last_main_sha=None
        while True:
            iteration_started=time.monotonic()
            fresh=read_json(args.config)
            e.trusted=fresh['trusted_keys']
            e.config['poll_seconds']=min(max(fresh.get('poll_seconds',2),2),2)
            status=e.cycle()
            try:
                def receive_available_release():
                    release_head=remote.head()
                    if release_head: receive_release(e,release_head)
                if config.get('receive_releases',True):
                    runtime_stage(state,status,'receive_release',receive_available_release)
                if config['role']=='leader' and config.get('release_repository') and time.monotonic()-last_release_check>5:
                    last_release_check=time.monotonic()
                    def check_approved_main():
                        nonlocal last_main_sha
                        repo=config['release_repository']
                        # Approved main only; never change a working tree or accept a research branch as software.
                        sha=subprocess.check_output(['git','-C',repo,'ls-remote','origin','refs/heads/main'],text=True,timeout=30).split()[0]
                        if sha!=last_main_sha:
                            subprocess.run(['git','-C',repo,'fetch','--no-tags','origin',sha],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
                            publish_release(e,repo,sha)
                            last_main_sha=sha
                    runtime_stage(state,status,'check_approved_main',check_approved_main)
            except Exception as error:
                status['error']={'stage':'release','message':str(error)};status['state']='error';write_json(state/'status.json',status)
            if args.command=='once': print(json.dumps(status,ensure_ascii=False));return
            failures=failures+1 if status['state']=='offline' else 0
            delay=poll_delay(config,status,failures,getattr(remote,'cooldown_until',0))
            # Keep the data poll cadence anchored to loop start when healthy. A slow
            # stage should trigger the next poll immediately, not add another full delay.
            elapsed=time.monotonic()-iteration_started
            remaining=max(0,delay-elapsed) if status['state']=='online' else delay
            time.sleep(remaining+random.random()*min(.1,delay/20))

if __name__=='__main__': main()
