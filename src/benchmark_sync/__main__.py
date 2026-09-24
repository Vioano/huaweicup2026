from __future__ import annotations
import argparse
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
    if config['role'] not in ('leader','member') or not 10<=config.get('poll_seconds',15)<=3600: raise ValueError('Invalid runtime role/poll interval')
    state=Path(config['state']);state.mkdir(parents=True,exist_ok=True)
    if args.command=='enqueue':
        print(enqueue(state,args.repo,args.commit,args.feed,config['actor']));return
    with exclusive_lock(state/'runtime.lock'):
        s=Signatures(config.get('node'))
        remote=GitHub(config['repository'],config.get('branch','benchmark-sync-v1'),state/'git-cache',actor=config['actor'],gh=config.get('gh','gh'))
        e=Engine(config,remote,s)
        if args.command=='publish-release':
            if config['role']!='leader': raise ValueError('Only central publisher may release code')
            print(json.dumps(publish_release(e,args.repo,args.commit),ensure_ascii=False));return
        failures=0;last_release_check=0
        while True:
            fresh=read_json(args.config)
            e.trusted=fresh['trusted_keys']
            status=e.cycle()
            try:
                if config.get('receive_releases',True) and remote.head(): receive_release(e,remote.head())
                if config['role']=='leader' and config.get('release_repository') and time.monotonic()-last_release_check>60:
                    repo=config['release_repository']
                    # Approved main only; never change a working tree or accept a research branch as software.
                    sha=subprocess.check_output(['git','-C',repo,'ls-remote','origin','refs/heads/main'],text=True,timeout=30).split()[0]
                    subprocess.run(['git','-C',repo,'fetch','--no-tags','origin',sha],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
                    publish_release(e,repo,sha);last_release_check=time.monotonic()
            except Exception as error:
                status['error']={'stage':'release','message':str(error)};status['state']='error';write_json(state/'status.json',status)
            if args.command=='once': print(json.dumps(status,ensure_ascii=False));return
            failures=failures+1 if status['state']=='offline' else 0
            delay=min(300,config.get('poll_seconds',15)*2**min(failures,5))
            delay=max(delay,getattr(remote,'cooldown_until',0)-time.time(),status.get('error',{}).get('retry_after',0) if status.get('error') else 0)
            time.sleep(delay+random.random()*min(3,delay/5))

if __name__=='__main__': main()
