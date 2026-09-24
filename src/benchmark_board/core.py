"""Append-only benchmark ledger. No solver/evaluator execution, no third-party dependencies."""
from __future__ import annotations
import hashlib, json, math, sqlite3, re, gzip, io
from pathlib import PurePosixPath
from datetime import datetime, timezone
from contextlib import contextmanager

MAX_BLOB = 64 * 1024 * 1024
METRICS = {'makespan_cycles': ('Makespan', '周期', False), 'baseline_speedup': ('相对官方单核', '×', True), 'solver_wall_seconds': ('求解耗时', '秒', False), 'evaluation_wall_seconds': ('外部复评耗时', '秒', False), 'ddr_bytes': ('调度搬运', '字节', False), 'spill_bytes': ('溢出搬运', '字节', False), 'extra_ddr_bytes': ('额外搬运', '字节', False), 'cache_gain': ('Cache 加速比', '×', True), 'cache_hit_rate': ('Cache 字节命中率', '%', True)}

def now(): return datetime.now(timezone.utc).isoformat()
def packed(obj): return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(data): return hashlib.sha256(data).hexdigest()
def number(x, positive=False): return type(x) in (int, float) and math.isfinite(x) and (x > 0 if positive else x >= 0)
def sha(x, size=64): return isinstance(x, str) and re.fullmatch('[0-9a-f]{%s}' % size, x) is not None

def safe_path(path):
    if not isinstance(path, str) or '\\' in path or ':' in path or any(p in ('..', '.git') for p in path.split('/')) or PurePosixPath(path).is_absolute():
        raise ValueError('unsafe artifact path')
    if not path.startswith(('results/', 'docs/', 'data/', 'tasks/')): raise ValueError('artifact outside allowed data directories')
    return path

def read_json_blob(data, path):
    if path.endswith('.gz'):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream: data = stream.read(MAX_BLOB + 1)
    if len(data) > MAX_BLOB: raise ValueError('artifact too large')
    return json.loads(data)

class Ledger:
    def __init__(self, state, manifest, calibrations=None):
        self.state = state; state.mkdir(parents=True, exist_ok=True)
        (state / 'blobs').mkdir(exist_ok=True)
        self.manifest = manifest; self.calibrations = calibrations or {}
        self.expected = {f['path']: f['sha256'] for f in manifest['files']}
        with self.connect() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS records(seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, attempt TEXT, revision INTEGER, body TEXT, UNIQUE(attempt,revision));
            CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, source TEXT, imported_at TEXT, count INTEGER);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, body TEXT, time TEXT);
            CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, body TEXT);
            ''')
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.state / 'ledger.sqlite3', timeout=15); db.row_factory = sqlite3.Row
        try:
            with db: yield db
        finally: db.close()
    def artifact(self, spec, loader, source):
        if not isinstance(spec, dict) or not sha(spec.get('sha256')): raise ValueError('artifact hash missing')
        path = safe_path(spec.get('path')); data = loader(path)
        if len(data) > MAX_BLOB or digest(data) != spec['sha256']: raise ValueError('artifact bytes/hash mismatch: ' + path)
        target = self.state / 'blobs' / spec['sha256']
        if not target.exists():
            temp = target.with_suffix('.tmp'); temp.write_bytes(data); temp.replace(target)
        return read_json_blob(data, path)
    def validate(self, raw, loader, source):
        r = json.loads(packed(raw)); p=r.get('problem'); case=r.get('case_id'); k=r.get('cores')
        if p not in ('P1','P2','P3') or case not in [f'{n:03d}' for n in range(1,101)] or type(k) is not int or k not in range(1,6): raise ValueError('invalid problem/case/cores')
        for field in ('attempt_id','run_id','algorithm_id','algorithm_name'):
            if not isinstance(r.get(field),str) or not r[field] or len(r[field])>200: raise ValueError('missing/invalid ' + field)
        if r.get('solver_commit') is not None and not sha(r.get('solver_commit'),40): raise ValueError('solver full commit required')
        if type(r.get('revision',1)) is not int or r.get('revision',1)<1: raise ValueError('positive revision required')
        r.setdefault('revision',1)
        if r.get('status') not in ('ok','failed','timeout','running','not_run','unsupported','withdrawn'): raise ValueError('unknown status')
        metrics=r.setdefault('metrics',{}); ev=r.get('evaluator',{}); identity=r.get('identity',{})
        for name,value in metrics.items():
            if name not in METRICS: raise ValueError('unknown metric '+name)
            if value is not None and not number(value, name=='makespan_cycles'): raise ValueError('bad metric '+name)
        if metrics.get('cache_hit_rate') is not None and metrics['cache_hit_rate']>1: raise ValueError('hit rate must be fraction 0..1')
        # All derived ratios are calculated from matching evidence below, never accepted from a CSV.
        metrics.pop('baseline_speedup',None); metrics.pop('cache_gain',None)
        r['eligible']=False; r['evidence']='reported'; r['admission_notes']=[]
        r['source']=source; r['imported_at']=now(); r['baseline_verified']=False; r['cache_pair_verified']=False
        if r['status'] != 'ok':
            for name in METRICS:
                if name not in ('solver_wall_seconds','evaluation_wall_seconds'): metrics[name]=None
            r['admission_notes'].append('未成功的尝试不参与最优选择'); return r
        if not number(metrics.get('makespan_cycles'),True): raise ValueError('successful record requires makespan')
        try:
            if not sha(r.get('solver_commit'),40): raise ValueError('求解器版本未知，保留报告但不入榜')
            if ev.get('route') == 'E2': raise ValueError('E2 不进入正式成绩')
            if ev.get('route') not in ('E0','E1'): raise ValueError('评价源未明确')
            if not sha(ev.get('commit'),40) or not ev.get('entrypoint'): raise ValueError('评价器固定版本/入口缺失')
            if identity.get('official_sha256')!=self.manifest['official_code_hash'] or identity.get('graph_sha256')!=self.expected['data/case_'+case+'.json'] or identity.get('config_sha256')!=self.expected['data/config.txt']: raise ValueError('不是当前冻结输入/配置/官方源码，隔离展示')
            if ev['route']=='E1':
                c=self.calibrations.get(ev.get('calibration_id'))
                if not c or any(c.get(a)!=b for a,b in [('commit',ev['commit']),('problem',p),('config_sha256',identity['config_sha256']),('runtime_id',r.get('runtime_id'))]) or case not in c.get('cases',[]) or k not in c.get('cores',[]): raise ValueError('E1 不在队长固定校准准入范围')
            arts=r.get('artifacts',{})
            plan=self.artifact(arts.get('plan'),loader,source)
            if arts['plan']['sha256']!=identity.get('plan_sha256'): raise ValueError('plan identity mismatch')
            if set(plan)!={'node_to_subgraph','core_schedules'}: raise ValueError('plan shape mismatch')
            result=self.artifact(arts.get('result'),loader,source)
            self.artifact(arts.get('run'),loader,source)  # real receipt bytes; semantics remain source-reported
            if type(result.get('makespan')) is not type(metrics['makespan_cycles']) or result['makespan']!=metrics['makespan_cycles']: raise ValueError('result/makespan or number type mismatch')
            if result.get('scene')!={'P1':'A','P2':'B','P3':'C'}[p] or result.get('num_cores')!=k: raise ValueError('result scene/core mismatch')
            # Derive memory metrics from official result, never caller's prettier numbers.
            movement=result.get('data_movement_bytes',{})
            metrics['ddr_bytes']=movement.get('scheduled_copy_bytes')
            metrics['spill_bytes']=movement.get('spill_added_copy_bytes')
            metrics['extra_ddr_bytes']=movement.get('added_copy_bytes')
            metrics['cache_hit_rate']=result.get('cache_stats',{}).get('hit_rate') if p=='P3' else None
            for m in ('ddr_bytes','spill_bytes','extra_ddr_bytes','cache_hit_rate'):
                if metrics[m] is not None and not number(metrics[m]): raise ValueError('invalid official metric')
            if metrics['cache_hit_rate'] is not None and metrics['cache_hit_rate']>1: raise ValueError('invalid official hit rate')
            r['eligible']=True; r['evidence']='artifacts_checked'
            r['admission_notes'].append('已核对固定提交的方案/结果/过程原件及冻结身份；不是重新执行或算法终验')
        except (ValueError,KeyError,TypeError,FileNotFoundError,json.JSONDecodeError) as error:
            r['admission_notes'].append(str(error))
        for field in ('baseline','cache_pair'):
            # A verified denominator can accompany a reported E0 numerator.
            # This only enables the explicit report preview, never admission.
            if not r['eligible'] and (field != 'baseline' or ev.get('route') != 'E0' or not self.compatible(r)):
                continue
            pair=r.get(field)
            if not pair: continue
            try:
                if any(pair.get(a)!=identity.get(a) for a in ('graph_sha256','config_sha256','official_sha256')): raise ValueError('pair identity mismatch')
                if pair.get('route')!='E0': raise ValueError('pair currently requires E0')
                result=self.artifact(pair.get('result'),loader,source)
                cycles=result.get('makespan')
                if not number(cycles,True): raise ValueError('invalid denominator')
                if field=='baseline':
                    if pair.get('entrypoint')!='singlecore_evaluate.evaluate_singlecore' or result.get('num_cores')!=1 or result.get('scene')!='A': raise ValueError('not official singlecore baseline')
                    metrics['baseline_speedup']=cycles/metrics['makespan_cycles']; r['baseline_verified']=True
                    if not r['eligible']:
                        r['admission_notes'].append('单核分母原件已核；加速比的多核分子仍为作者报告，仅用于报告预览')
                else:
                    if p!='P3' or pair.get('plan_sha256')!=identity.get('plan_sha256') or pair.get('cores')!=k or result.get('scene')!='B' or result.get('num_cores')!=k: raise ValueError('Cache 必须同计划、同核数 P2/P3 配对')
                    metrics['cache_gain']=cycles/metrics['makespan_cycles']; r['cache_pair_verified']=True
            except (ValueError,KeyError,TypeError,FileNotFoundError,json.JSONDecodeError) as error: r['admission_notes'].append(field+': '+str(error))
        return r
    def ingest(self, feed, loader, source):
        if feed.get('submission_version') is not None:
            from protocol import validate_feed
            validate_feed(feed, submission=True)
        if feed.get('schema_version')!=1 or not isinstance(feed.get('records'),list) or len(feed['records'])>5000: raise ValueError('expected schema_version=1, <=5000 records')
        batch=digest(packed({'feed':feed,'source':source}).encode())
        with self.connect() as db:
            if db.execute('SELECT 1 FROM batches WHERE id=?',(batch,)).fetchone(): return {'duplicate':True,'added':0}
        rows=[]
        for raw in feed['records']:
            rid=digest(packed(raw).encode()); r=self.validate(raw,loader,source); r['id']=rid; rows.append(r)
        with self.connect() as db:
            count=0
            for r in rows:
                old=db.execute('SELECT id FROM records WHERE attempt=? AND revision=?',(r['attempt_id'],r['revision'])).fetchone()
                if old:
                    if old['id']!=r['id']: raise ValueError('同 attempt/revision 内容冲突：必须追加新 revision，禁止覆盖')
                    continue
                previous=db.execute('SELECT body FROM records WHERE attempt=? ORDER BY revision DESC LIMIT 1',(r['attempt_id'],)).fetchone()
                if previous:
                    oldr=json.loads(previous['body'])
                    if any(oldr[f]!=r[f] for f in ('problem','case_id','cores','algorithm_id','run_id','solver_commit')): raise ValueError('attempt identity cannot change')
                db.execute('INSERT INTO records(id,attempt,revision,body) VALUES(?,?,?,?)',(r['id'],r['attempt_id'],r['revision'],packed(r)))
                db.execute('INSERT INTO events(kind,body,time) VALUES(?,?,?)',('record',packed({'id':r['id'],'problem':r['problem'],'case_id':r['case_id'],'cores':r['cores'],'eligible':r['eligible']}),now()));count+=1
            db.execute('INSERT INTO batches VALUES(?,?,?,?)',(batch,packed(source),now(),count))
        return {'added':count,'batch':batch}
    def source_status(self, name, data):
        with self.connect() as db: db.execute('INSERT OR REPLACE INTO sources VALUES(?,?)',(name,packed(data)))
    def records(self, filters=None):
        with self.connect() as db: rows=[dict(json.loads(x['body']),sequence=x['seq']) for x in db.execute('SELECT * FROM records ORDER BY seq')]
        for key,value in (filters or {}).items():
            if value not in (None,'','all'): rows=[r for r in rows if str(r.get(key))==str(value)]
        return rows
    def compatible(self, r):
        ident=r.get('identity',{})
        return ident.get('official_sha256')==self.manifest['official_code_hash'] and ident.get('config_sha256')==self.expected.get('data/config.txt') and ident.get('graph_sha256')==self.expected.get('data/case_'+r['case_id']+'.json')
    def snapshot(self, algorithm=None, run=None, include_reported=False):
        allrows=self.records(); latest={}
        for r in allrows:
            if r['attempt_id'] not in latest or r['revision']>latest[r['attempt_id']]['revision']: latest[r['attempt_id']]=r
        groups={}
        for r in latest.values():
            if algorithm and r['algorithm_id']!=algorithm: continue
            if run and r['run_id']!=run: continue
            groups.setdefault((r['problem'],r['case_id'],r['cores']),[]).append(r)
        cells=[]
        for p in ('P1','P2','P3'):
            for n in range(1,101):
                for k in range(1,6):
                    rows=groups.get((p,f'{n:03d}',k),[])
                    candidates=[r for r in rows if r['status']=='ok' and (r['eligible'] or (include_reported and r.get('evaluator',{}).get('route')=='E0' and self.compatible(r)))]
                    # Prefer admitted records; reports are preview only and never displace admitted best.
                    candidates.sort(key=lambda r:(not r['eligible'],r['metrics']['makespan_cycles'],r['id']))
                    best=candidates[0] if candidates else None
                    cells.append({'problem':p,'case_id':f'{n:03d}','cores':k,'best':best,'attempts':len(rows),'status':('ok' if best and best['eligible'] else 'reported' if best else ('reported' if rows[-1]['status']=='ok' else rows[-1]['status']) if rows else 'not_run')})
        with self.connect() as db:
            cursor=db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
            sources={x['id']:json.loads(x['body']) for x in db.execute('SELECT * FROM sources')}
        return {'schema_version':1,'cursor':cursor,'as_of':now(),'cells':cells,'sources':sources,'latest_imported_at':max((r['imported_at'] for r in allrows),default=None),'latest_observed_at':max((r.get('observed_at') for r in allrows if r.get('observed_at')),default=None),'record_count':len(allrows),'algorithms':sorted({r['algorithm_id'] for r in allrows}),'runs':sorted({r['run_id'] for r in allrows}),'metrics':METRICS,'selection':'历史最优组合：仅同问题/图/核数/冻结配置；不是单一算法的全量实验成绩。切换指标不会换赢家。'}
    def events(self, after, limit=200):
        with self.connect() as db: rows=db.execute('SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?',(after,min(limit,1000))).fetchall()
        return [{'cursor':x['seq'],'type':x['kind'],'time':x['time'],'data':json.loads(x['body'])} for x in rows]
