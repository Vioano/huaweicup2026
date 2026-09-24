"""Local read-only HTTP/Agent interface; import published data only, never run benchmarks."""
from __future__ import annotations
import argparse, fnmatch, json, mimetypes, re, subprocess, threading, time, traceback
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from core import Ledger, now, packed, sha, safe_path, MAX_BLOB

ROOT=Path(__file__).resolve().parents[2]
WEB=Path(__file__).parent/'web'
REPO='huaweibei123/huaweicup2026'

def git(repo,*args,timeout=45):
    return subprocess.run(['git','-C',str(repo),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=timeout).stdout

def blob(repo,commit,path):
    safe_path(path)
    size=int(git(repo,'cat-file','-s',commit+':'+path))
    if size>MAX_BLOB: raise ValueError('oversized artifact')
    return git(repo,'show',commit+':'+path)

def load_feed(ledger,repo,commit,path):
    if not sha(commit,40): raise ValueError('full source commit required')
    data=blob(repo,commit,path)
    if len(data)>8*1024*1024: raise ValueError('feed too large')
    return ledger.ingest(json.loads(data),lambda p:blob(repo,commit,p),{'repo':REPO,'commit':commit,'path':path,'url':f'https://github.com/{REPO}/blob/{commit}/{path}'})

def sync_once(ledger,repo,sources):
    for s in sources:
        started=now(); name=s['id']
        try:
            ref=s['ref']
            if not re.fullmatch(r'[A-Za-z0-9_./-]+',ref) or '..' in ref: raise ValueError('bad source ref')
            found=git(repo,'ls-remote','origin','refs/heads/'+ref).decode().split()
            if not found: raise ValueError('source branch not published')
            commit=found[0]
            with ledger.connect() as db: prior=db.execute('SELECT body FROM sources WHERE id=?',(name,)).fetchone()
            prior=json.loads(prior['body']) if prior else {}
            if prior.get('commit')==commit and prior.get('status') in ('ok','waiting_feed'):
                prior.update(checked_at=now());ledger.source_status(name,prior);continue
            try: git(repo,'cat-file','-e',commit+'^{commit}')
            except subprocess.CalledProcessError: git(repo,'fetch','--no-tags','origin',commit,timeout=90)
            paths=git(repo,'ls-tree','-r','--name-only',commit,'--',s['prefix']).decode().splitlines()
            paths=[p for p in paths if fnmatch.fnmatch(p,s['prefix'].rstrip('/')+'/**/board-feed*.json') or (p.startswith(s['prefix'].rstrip('/')+'/') and Path(p).name.startswith('board-feed') and p.endswith('.json'))]
            if len(paths)>300: raise ValueError('source feed count exceeds 300; scope review needed')
            results=[load_feed(ledger,repo,commit,path) for path in paths]
            ledger.source_status(name,{'status':'ok' if paths else 'waiting_feed','ref':ref,'commit':commit,'checked_at':now(),'started_at':started,'feeds':len(paths),'added':sum(r['added'] for r in results),'message':'已接收固定数据' if paths else '分支可读，等待发布 board-feed；不等于队友未运行'})
        except Exception as e:
            ledger.source_status(name,{'status':'error','checked_at':now(),'started_at':started,'ref':s['ref'],'message':type(e).__name__+': '+str(e)[:250]})

def make_handler(ledger):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,data,status=200,ctype='application/json; charset=utf-8',headers=None):
            payload=packed(data).encode() if not isinstance(data,bytes) else data
            self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            for k,v in (headers or {}).items(): self.send_header(k,v)
            self.end_headers();self.wfile.write(payload)
        def do_GET(self):
            if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'): self.send({'error':'loopback host required'},403);return
            u=urlparse(self.path);q={k:v[-1] for k,v in parse_qs(u.query).items()};path=u.path
            try:
                if path=='/api/v1/health':
                    with ledger.connect() as db:
                        sources={r['id']:json.loads(r['body']) for r in db.execute('SELECT * FROM sources')}
                        count=db.execute('SELECT count(*) FROM records').fetchone()[0]
                    return self.send({'status':'ok','time':now(),'records':count,'sources':sources,'read_only':True})
                if path=='/api/v1/cells':
                    data=ledger.snapshot(q.get('algorithm'),q.get('run'),q.get('include_reported')=='true')
                    for key in ('problem','case_id','cores'):
                        if q.get(key): data['cells']=[c for c in data['cells'] if str(c[key])==q[key]]
                    return self.send(data)
                if path=='/api/v1/events':
                    after=max(0,int(q.get('after',0)));deadline=time.monotonic()+min(25,max(0,int(q.get('wait',0))))
                    while True:
                        events=ledger.events(after)
                        if events or time.monotonic()>=deadline: break
                        time.sleep(.5)
                    return self.send({'events':events,'next_cursor':events[-1]['cursor'] if events else after})
                if path=='/api/v1/records':
                    rows=ledger.records({k:q.get(k) for k in ('problem','case_id','cores','algorithm_id','run_id')})
                    start=max(0,int(q.get('offset',0)));limit=min(500,max(1,int(q.get('limit',100))))
                    return self.send({'records':rows[start:start+limit],'total':len(rows),'next_offset':start+limit if start+limit<len(rows) else None})
                if path.startswith('/api/v1/records/'):
                    rows=[r for r in ledger.records() if r['id']==path.rsplit('/',1)[-1]]
                    return self.send(rows[0] if rows else {'error':'not found'},200 if rows else 404)
                if path=='/api/v1/catalog':
                    return self.send(json.loads((ROOT/'docs/benchmarks/algorithm-registry.json').read_text()))
                if path=='/api/v1/schema': return self.send(json.loads((ROOT/'docs/benchmarks/board-feed.schema.json').read_text()))
                if path.startswith('/api/v1/blobs/'):
                    key=path.rsplit('/',1)[-1]
                    if not sha(key) or not (ledger.state/'blobs'/key).is_file(): return self.send({'error':'not found'},404)
                    return self.send((ledger.state/'blobs'/key).read_bytes(),ctype='application/octet-stream',headers={'Content-Disposition':'attachment; filename="'+key+'"'})
                files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/agent':'agent.html'}
                if path in files:
                    f=WEB/files[path];return self.send(f.read_bytes(),ctype={'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[f.suffix[1:]])
                self.send({'error':'not found'},404)
            except (ValueError,KeyError) as e: self.send({'error':str(e)},400)
        def do_POST(self): self.send({'error':'Read-only HTTP. Publish immutable feed via your branch; captain imports verified commit.'},405)
    return Handler

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,default=ROOT);p.add_argument('--state',type=Path,default=ROOT/'output/benchmark-board');sub=p.add_subparsers(dest='command',required=True)
    i=sub.add_parser('import');i.add_argument('--commit',required=True);i.add_argument('--feed',required=True)
    s=sub.add_parser('serve');s.add_argument('--port',type=int,default=52341);s.add_argument('--sync-interval',type=int,default=120);s.add_argument('--no-sync',action='store_true')
    sub.add_parser('sync');args=p.parse_args()
    manifest=json.loads((ROOT/'docs/a/source-manifest.json').read_text())
    admission=ROOT/'docs/benchmarks/board-calibrations.json';ledger=Ledger(args.state,manifest,json.loads(admission.read_text()) if admission.exists() else {})
    sources=json.loads((ROOT/'docs/benchmarks/board-sources.json').read_text())
    if args.command=='import': print(packed(load_feed(ledger,args.repo,args.commit,args.feed)));return
    if args.command=='sync':sync_once(ledger,args.repo,sources);print(packed({'done':True}));return
    if not args.no_sync:
        def worker():
            while True:
                sync_once(ledger,args.repo,sources);time.sleep(max(60,args.sync_interval))
        threading.Thread(target=worker,daemon=True).start()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(ledger));server.daemon_threads=True
    (args.state/'service.json').write_text(packed({'url':f'http://127.0.0.1:{args.port}','started_at':now(),'sources_poll_seconds':None if args.no_sync else max(60,args.sync_interval)}))
    print(f'Benchmark board: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
