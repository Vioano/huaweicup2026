"""One-time standalone Windows/macOS bootstrap; downloads only the signed small release.
Fetch this file from the fixed commit announced by the captain, then run python -X utf8 bootstrap.py --state <outside-repo> --watch-repo <research-repo>.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

REPO='huaweibei123/huaweicup2026'
LEADER='nikolastarx'
PUBLIC='-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEA3vXcerw176p5tuGtifEAemTBTyzy472zUTMWxSivATU=\n-----END PUBLIC KEY-----\n'
BRANCH='benchmark-sync-v1'
MAXIMUM=8*1024*1024

def canonical(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def sha(v): return hashlib.sha256(v).hexdigest()
def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp');temporary.write_bytes(data);os.replace(temporary,path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True);parser.add_argument('--watch-repo',type=Path,action='append',default=[])
    args=parser.parse_args()
    if not (3,12)<=sys.version_info[:2]<(3,13): raise SystemExit('Use the project Python 3.12 interpreter.')
    node=shutil.which('node');gh=shutil.which('gh')
    if not node or not gh: raise SystemExit('Existing Node.js and authenticated gh are required; no packages were installed.')
    state=args.state.resolve()
    for parent in (state,*state.parents):
        if (parent/'.git').exists(): raise SystemExit('Sync state and private key must be outside all Git workspaces.')
    state.mkdir(parents=True,exist_ok=True);state.chmod(0o700)
    token=subprocess.check_output([gh,'auth','token','--hostname','github.com'],stderr=subprocess.DEVNULL,text=True).strip()
    def request(path,raw=False):
        request=urllib.request.Request('https://api.github.com'+path,headers={
            'Authorization':'Bearer '+token,'Accept':'application/vnd.github.raw+json' if raw else 'application/vnd.github+json',
            'X-GitHub-Api-Version':'2022-11-28','User-Agent':'benchmark-sync-bootstrap/1'})
        with urllib.request.urlopen(request,timeout=45) as response: data=response.read(MAXIMUM+1)
        if len(data)>MAXIMUM: raise ValueError('Bootstrap response exceeds limit')
        return data if raw else json.loads(data)
    actor=request('/user')['login'].lower()
    if actor==LEADER: raise SystemExit('Captain deployment uses the reviewed leader configuration, not member bootstrap.')
    head=request('/repos/'+REPO+'/git/ref/heads/'+BRANCH)['object']['sha']
    def file(path): return request('/repos/'+REPO+'/contents/'+urllib.parse.quote(path,safe='/')+'?ref='+head,True)
    envelope=json.loads(file('channels/release.json'))
    if set(envelope)!={'schema_version','project','domain','issuer','key_sha256','payload','signature'} or any(envelope.get(k)!=v for k,v in {
        'schema_version':1,'project':'huaweicup2026-benchmark-board','domain':'release','issuer':LEADER,'key_sha256':sha(PUBLIC.encode())}.items()):
        raise ValueError('Untrusted release envelope')
    content={k:v for k,v in envelope.items() if k!='signature'}
    verifier="const c=require('node:crypto'),f=require('node:fs'),v=JSON.parse(f.readFileSync(0,'utf8'));process.exit(c.verify(null,Buffer.from(v.message,'base64'),v.public,Buffer.from(v.signature,'base64'))?0:1);"
    subprocess.run([node,'-e',verifier],input=canonical({'public':PUBLIC,'message':base64.b64encode(canonical(content)).decode(),'signature':envelope['signature']}),check=True)
    channel=envelope['payload'];m=channel['manifest']
    if channel['object']!='objects/'+m['release_id'] or not re.fullmatch('[0-9a-f]{64}',m['release_id']): raise ValueError('Release identity mismatch')
    data=file(channel['object'])
    if len(data)!=m['size'] or sha(data)!=m['release_id']: raise ValueError('Release ZIP hash mismatch')
    release=state/'releases'/m['release_id'];release.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if len(archive.namelist())!=len(set(archive.namelist())) or set(archive.namelist())!=set(m['files']): raise ValueError('Release entries mismatch')
        total=0
        for entry in archive.infolist():
            name=entry.filename
            if name.startswith('/') or '\\' in name or ':' in name or any(p in ('','..','.git') for p in name.split('/')) or not name.startswith(('src/benchmark_board/','src/benchmark_sync/','docs/')):
                raise ValueError('Unsafe release path')
            if (entry.external_attr>>16)&0o170000 not in (0,0o100000): raise ValueError('Non-regular release file')
            spec=m['files'][name];total+=entry.file_size
            if total>MAXIMUM*4 or entry.file_size!=spec['size']: raise ValueError('Expanded release limit')
            value=archive.read(entry)
            if sha(value)!=spec['sha256']: raise ValueError('Release file hash mismatch')
            write(release/name,value)
    write(release/'release.json',canonical(m))
    key=state/'identity.pem'
    crypto=release/'src/benchmark_sync/crypto.mjs'
    operation='public' if key.exists() else 'generate'
    public=json.loads(subprocess.check_output([node,str(crypto)],input=canonical({'operation':operation,'privateKeyPath':str(key)})))['public_key']
    config_path=state/'config.json'
    config=json.loads(config_path.read_bytes()) if config_path.exists() else {
        'schema_version':1,'state':str(state),'actor':actor,'leader':LEADER,'role':'member','repository':REPO,'branch':BRANCH,
        'private_key':str(key),'trusted_keys':{LEADER:PUBLIC,actor:public},'port':52341,'poll_seconds':15,'receive_releases':True,
        'watch_repositories':[str(p.resolve()) for p in args.watch_repo]}
    if config['actor']!=actor or config['role']!='member': raise ValueError('Existing configuration belongs to a different role/user')
    config.update(python=sys.executable,node=node,gh=gh)
    write(config_path,canonical(config))
    bootstrap={'release_id':m['release_id'],'code_commit':m['code_commit'],'path':str(release),'_channel':envelope}
    write(state/'bootstrap.json',canonical(bootstrap))
    desired_path=state/'software/desired.json'
    if desired_path.exists():
        previous=json.loads(desired_path.read_bytes())['_channel']['payload']
        if channel['generation']<previous['generation'] or (channel['generation']==previous['generation'] and channel!=previous):
            raise ValueError('Bootstrap refused to roll back existing accepted release')
    write(desired_path,canonical(bootstrap))
    launcher='''import json, pathlib, subprocess, sys\ns=pathlib.Path(__file__).resolve().parent\na=s/"software/active.json"\nc=json.loads((s/"config.json").read_bytes())\nb=json.loads((a if a.exists() else s/"bootstrap.json").read_bytes())\nsys.exit(subprocess.call([c["python"],"-X","utf8","-u","-m","src.benchmark_sync.supervisor","--config",str(s/"config.json"),"--bootstrap",str(s/"bootstrap.json")],cwd=b["path"]))\n'''
    write(state/'start.py',launcher.encode())
    subprocess.run([sys.executable,'-X','utf8','-m','src.benchmark_sync','--config',str(config_path),'once'],cwd=release,check=True)
    print(json.dumps({'actor':actor,'public_key':public,'public_sha256':sha(public.encode()),'release_id':m['release_id'],
                      'next':'Send this PUBLIC key once in Issue 33 under your own account, then hand off the existing website port and install/start the supervisor. Never send identity.pem.',
                      'start_command':[sys.executable,'-X','utf8',str(state/'start.py')]},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
