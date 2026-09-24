"""Append-only benchmark ledger. No solver/evaluator execution, no third-party dependencies."""
from __future__ import annotations
import hashlib, json, math, sqlite3, re, gzip, io
from collections import Counter
from pathlib import PurePosixPath
from datetime import datetime, timezone
from contextlib import contextmanager
from composites import COMPOSITES, member_row, verified as composite_verified

try:
    import orjson as _fast_json
except ImportError:
    _fast_json = None

MAX_BLOB = 64 * 1024 * 1024
MAX_EXPANDED_JSON = 128 * 1024 * 1024  # Complete official timelines can exceed 64 MiB.
METRICS = {'makespan_cycles': ('Makespan', '周期', False), 'baseline_speedup': ('相对官方单核', '×', True), 'solver_wall_seconds': ('求解耗时', '秒', False), 'evaluation_wall_seconds': ('外部复评耗时', '秒', False), 'ddr_bytes': ('调度搬运', '字节', False), 'spill_bytes': ('溢出搬运', '字节', False), 'extra_ddr_bytes': ('额外搬运', '字节', False), 'cache_gain': ('Cache 加速比', '×', True), 'cache_hit_rate': ('Cache 字节命中率', '%', True)}

def now(): return datetime.now(timezone.utc).isoformat()
def packed(obj): return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(data): return hashlib.sha256(data).hexdigest()
def number(x, positive=False): return type(x) in (int, float) and math.isfinite(x) and (x > 0 if positive else x >= 0)
def sha(x, size=64): return isinstance(x, str) and re.fullmatch('[0-9a-f]{%s}' % size, x) is not None

def official_scene(result, problem):
    # The frozen P3 evaluator calls its base execution scene B, not C.
    if problem == 'P3':
        return result.get('scene') == 'B' and type(result.get('problem')) is int and result['problem'] == 3 and result.get('cache_mode') == 'read_only'
    return result.get('scene') == ('A' if problem == 'P1' else 'B') and result.get('problem') in (None, int(problem[1])) and result.get('cache_mode') is None and 'cache_stats' not in result

def safe_path(path):
    if not isinstance(path, str) or '\\' in path or ':' in path or any(p in ('..', '.git') for p in path.split('/')) or PurePosixPath(path).is_absolute():
        raise ValueError('unsafe artifact path')
    if not path.startswith(('results/', 'docs/', 'data/', 'tasks/')): raise ValueError('artifact outside allowed data directories')
    return path

def read_json_blob(data, path):
    if path.endswith('.gz'):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream: data = stream.read(MAX_EXPANDED_JSON + 1)
    if len(data) > MAX_EXPANDED_JSON: raise ValueError('expanded artifact too large')
    return _fast_json.loads(data) if _fast_json is not None else json.loads(data)

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
    def artifact(self, spec, loader, source, parsed=None):
        if not isinstance(spec, dict) or not sha(spec.get('sha256')): raise ValueError('artifact hash missing')
        path = safe_path(spec.get('path')); data = loader(path)
        if len(data) > MAX_BLOB or digest(data) != spec['sha256']: raise ValueError('artifact bytes/hash mismatch: ' + path)
        target = self.state / 'blobs' / spec['sha256']
        if not target.exists():
            temp = target.with_suffix('.tmp'); temp.write_bytes(data); temp.replace(target)
        # A full 500-cell feed repeats each official single-core baseline five
        # times. Verify every reference's bytes, then parse identical content once.
        if parsed is not None and spec['sha256'] in parsed:
            return parsed[spec['sha256']]
        value = read_json_blob(data, path)
        if parsed is not None:
            parsed[spec['sha256']] = value
        return value
    def validate(self, raw, loader, source, parsed=None):
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
            plan=self.artifact(arts.get('plan'),loader,source,parsed)
            if arts['plan']['sha256']!=identity.get('plan_sha256'): raise ValueError('plan identity mismatch')
            if set(plan)!={'node_to_subgraph','core_schedules'}: raise ValueError('plan shape mismatch')
            result=self.artifact(arts.get('result'),loader,source,parsed)
            self.artifact(arts.get('run'),loader,source,parsed)  # real receipt bytes; semantics remain source-reported
            if type(result.get('makespan')) is not type(metrics['makespan_cycles']) or result['makespan']!=metrics['makespan_cycles']: raise ValueError('result/makespan or number type mismatch')
            if not official_scene(result,p) or result.get('num_cores')!=k: raise ValueError('result problem/cache/scene/core mismatch')
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
                result=self.artifact(pair.get('result'),loader,source,parsed)
                cycles=result.get('makespan')
                if not number(cycles,True): raise ValueError('invalid denominator')
                if field=='baseline':
                    if pair.get('entrypoint')!='singlecore_evaluate.evaluate_singlecore' or result.get('num_cores')!=1 or result.get('scene')!='A': raise ValueError('not official singlecore baseline')
                    metrics['baseline_speedup']=cycles/metrics['makespan_cycles']; r['baseline_verified']=True
                    if not r['eligible']:
                        r['admission_notes'].append('单核分母原件已核；加速比的多核分子仍为作者报告，仅用于报告预览')
                else:
                    if p!='P3' or pair.get('plan_sha256')!=identity.get('plan_sha256') or pair.get('cores')!=k or not official_scene(result,'P2') or result.get('num_cores')!=k: raise ValueError('Cache 必须同计划、同核数 P2/P3 配对')
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
        rows=[]; parsed={}
        for raw in feed['records']:
            rid=digest(packed(raw).encode()); r=self.validate(raw,loader,source,parsed); r['id']=rid; rows.append(r)
        with self.connect() as db:
            # Another importer may have committed this batch during byte validation.
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM batches WHERE id=?',(batch,)).fetchone():
                return {'duplicate':True,'added':0}
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
    def records_by_ids(self, identifiers):
        """Read only a just-submitted batch when calculating its admission receipt."""
        ids=list(identifiers)
        rows=[]
        with self.connect() as db:
            for start in range(0,len(ids),400):
                chunk=ids[start:start+400]
                marks=','.join('?' for _ in chunk)
                for item in db.execute(f'SELECT seq,body FROM records WHERE id IN ({marks})',chunk):
                    rows.append(dict(json.loads(item['body']),sequence=item['seq']))
        return rows
    def compatible(self, r):
        ident=r.get('identity',{})
        return ident.get('official_sha256')==self.manifest['official_code_hash'] and ident.get('config_sha256')==self.expected.get('data/config.txt') and ident.get('graph_sha256')==self.expected.get('data/case_'+r['case_id']+'.json')
    def health(self):
        with self.connect() as db:
            sources={r['id']:json.loads(r['body']) for r in db.execute('SELECT * FROM sources')}
            count=db.execute('SELECT count(*) FROM records').fetchone()[0]
        return {'status':'ok','time':now(),'records':count,'sources':sources,'read_only':True,'mode':'local_ledger'}
    def snapshot(self, algorithm=None, run=None, include_reported=False):
        with self.connect() as db:
            db.execute('BEGIN')
            rows=[dict(json.loads(x['body']),sequence=x['seq']) for x in db.execute('SELECT * FROM records ORDER BY seq')]
            cursor=db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
            sources={x['id']:json.loads(x['body']) for x in db.execute('SELECT * FROM sources')}
        return project_records(rows,self.manifest,cursor,sources,algorithm,run,include_reported)
    def events(self, after, limit=200):
        with self.connect() as db: rows=db.execute('SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?',(after,min(limit,1000))).fetchall()
        return [{'cursor':x['seq'],'type':x['kind'],'time':x['time'],'data':json.loads(x['body'])} for x in rows]

def batch_candidates(allrows, problem, cores, case_ids, composites=COMPOSITES):
    """Rank real runs or explicitly fingerprinted collections on one case set."""
    if problem not in ('P1','P2','P3') or cores not in range(1,6):
        raise ValueError('invalid problem or core count')
    cases=set(case_ids)
    if not cases or not cases <= {f'{n:03d}' for n in range(1,101)}:
        raise ValueError('cases must be official case IDs 001–100')
    latest={}
    for r in allrows:
        if r['attempt_id'] not in latest or r['revision']>latest[r['attempt_id']]['revision']:
            latest[r['attempt_id']]=r
    groups={}
    for r in latest.values():
        if r['problem']==problem:
            groups.setdefault(r['run_id'],[]).append(r)
    composite_specs={}
    for spec in composites:
        if spec['problem']!=problem: continue
        rows=[r for r in latest.values() if member_row(r,spec)]
        if rows:
            groups[spec['id']]=rows
            composite_specs[spec['id']]=spec
    candidates=[]
    for run,all_run_rows in groups.items():
        spec=composite_specs.get(run)
        collection_verified=composite_verified(all_run_rows,spec) if spec else None
        attempts_per_cell=Counter((r['case_id'],r['cores']) for r in all_run_rows)
        one_attempt_per_cell=all(count==1 for count in attempts_per_cell.values())
        sources={(r['algorithm_id'],r.get('solver_commit')) for r in all_run_rows}
        entrypoints=set()
        for r in all_run_rows:
            solver=(r.get('provenance') or {}).get('solver') or {}
            source=solver.get('source') or {}
            entrypoints.add((source.get('path'),source.get('entrypoint')))
        fixed_entrypoint=len(entrypoints)==1 and all(isinstance(value,str) and value for value in next(iter(entrypoints)))
        full_best={}
        for r in all_run_rows:
            if r['status']!='ok' or not r['eligible']: continue
            key=(r['case_id'],r['cores'])
            old=full_best.get(key)
            if old is None or (r['metrics']['makespan_cycles'],r['id'])<(old['metrics']['makespan_cycles'],old['id']):
                full_best[key]=r
        rows=[r for r in all_run_rows if r['cores']==cores and r['case_id'] in cases]
        best={}
        for r in rows:
            if r['status']!='ok' or not r['eligible']: continue
            old=best.get(r['case_id'])
            if old is None or (r['metrics']['makespan_cycles'],r['id'])<(old['metrics']['makespan_cycles'],old['id']):
                best[r['case_id']]=r
        def values(metric, baseline=False):
            return [r['metrics'][metric] for r in best.values()
                    if (not baseline or r.get('baseline_verified')) and number(r['metrics'].get(metric),baseline)]
        ratios=values('baseline_speedup',True)
        walls=values('solver_wall_seconds')
        single=len(sources)==1 and all(sha(commit,40) for _,commit in sources)
        complete=len(ratios)==len(cases) and single and (not spec or collection_verified)
        full_ratios={k:[r['metrics'].get('baseline_speedup') for (case,core),r in full_best.items()
                        if core==k and r.get('baseline_verified') and number(r['metrics'].get('baseline_speedup'),True)]
                     for k in range(1,6)}
        full_scored=sum(map(len,full_ratios.values()))
        full_complete=len(full_best)==500 and single and fixed_entrypoint and one_attempt_per_cell and (not spec or collection_verified)
        candidates.append({'run_id':run,'algorithm_ids':sorted({a for a,_ in sources}),
            'composite':bool(spec),'composite_verified':collection_verified,
            'composite_label':spec['label'] if spec else None,
            'component_runs':[member[0] for member in spec['members']] if spec else [],
            'manifest_url':('https://github.com/huaweibei123/huaweicup2026/blob/'+spec['source_commit']+'/'+spec['manifest_path']) if spec else None,
            'solver_commits':sorted({c for _,c in sources if c}), 'single_source':single,
            'fixed_entrypoint':fixed_entrypoint,'one_attempt_per_cell':one_attempt_per_cell,
            'valid_count':len(best),'scored_count':len(ratios),'target_count':len(cases),
            'mean_speedup':sum(ratios)/len(ratios) if ratios else None,
            'mean_solver_seconds':sum(walls)/len(walls) if walls else None,'solver_count':len(walls),
            'complete':complete,'missing_cases':sorted(cases-set(best)),
            'full_valid_count':len(full_best),'full_scored_count':full_scored,
            'full_complete':full_complete,
            'full_mean_speedup':sum(full_ratios[cores])/100 if len(full_ratios[cores])==100 else None,
            'record_count':len(all_run_rows),'scope_attempts':len(rows),
            'status_counts':{status:sum(r['status']==status for r in rows) for status in sorted({r['status'] for r in rows})}})
    full_all=sorted((r for r in candidates if r['full_complete']),
                key=lambda r:(r['full_mean_speedup'] is None,-(r['full_mean_speedup'] or 0),r['run_id']))
    complete=sorted((r for r in candidates if r['complete']),key=lambda r:(-r['mean_speedup'],r['run_id']))
    partial=sorted((r for r in candidates if not r['complete']),key=lambda r:(-r['scored_count'],-r['valid_count'],r['run_id']))
    return {'problem':problem,'cores':cores,'case_ids':sorted(cases),'target_count':len(cases),
            'full_complete_count':len(full_all),'full':full_all[:3],
            'complete_count':len(complete),'partial_count':len(partial),'complete':complete[:3],'partial':partial[:3],
            'batches':full_all+[r for r in complete+partial if not r['full_complete']],
            'ranking':'主成绩候选须同一批次，或有固定清单及原始记录指纹的复合批次；同一算法和求解器提交在本题100图×1–5核均已核，每格仅一次尝试。逐核均值为逐例算术平均。筛选子集只作预览，历史逐格最佳不参与。'}

def project_records(allrows, manifest, cursor, sources, algorithm=None, run=None, include_reported=False, composites=COMPOSITES):
    """Shared selection for local original checking and central read-only mirrors."""
    expected={f["path"]:f["sha256"] for f in manifest["files"]}
    def compatible(r):
        ident=r.get("identity",{})
        return ident.get("official_sha256")==manifest["official_code_hash"] and ident.get("config_sha256")==expected.get("data/config.txt") and ident.get("graph_sha256")==expected.get("data/case_"+r["case_id"]+".json")
    latest={}
    for r in allrows:
        if r['attempt_id'] not in latest or r['revision']>latest[r['attempt_id']]['revision']: latest[r['attempt_id']]=r
    selected_composite=next((spec for spec in composites if spec['id']==run),None)
    groups={}
    for r in latest.values():
        if algorithm and r['algorithm_id']!=algorithm: continue
        if run and not (member_row(r,selected_composite) if selected_composite else r['run_id']==run): continue
        groups.setdefault((r['problem'],r['case_id'],r['cores']),[]).append(r)
    cells=[]
    for p in ('P1','P2','P3'):
        for n in range(1,101):
            for k in range(1,6):
                rows=groups.get((p,f'{n:03d}',k),[])
                candidates=[r for r in rows if r['status']=='ok' and (r['eligible'] or (include_reported and r.get('evaluator',{}).get('route')=='E0' and compatible(r)))]
                # Prefer admitted records; reports are preview only and never displace admitted best.
                candidates.sort(key=lambda r:(not r['eligible'],r['metrics']['makespan_cycles'],r['id']))
                best=candidates[0] if candidates else None
                latest_report=next((r for r in reversed(rows) if r['status']=='ok' and not r['eligible']),None)
                missing=[a for a in ('plan','result','run') if not latest_report.get('artifacts',{}).get(a)] if latest_report else []
                cells.append({'problem':p,'case_id':f'{n:03d}','cores':k,'best':best,'attempts':len(rows),'missing_artifacts':missing,'status':('ok' if best and best['eligible'] else 'reported' if best else ('reported' if rows[-1]['status']=='ok' else rows[-1]['status']) if rows else 'not_run')})
    runs={r['run_id'] for r in allrows}
    runs.update(spec['id'] for spec in composites if any(member_row(r,spec) for r in latest.values()))
    return {'schema_version':1,'cursor':cursor,'as_of':now(),'cells':cells,'sources':sources,'latest_imported_at':max((r['imported_at'] for r in allrows),default=None),'latest_observed_at':max((r.get('observed_at') for r in allrows if r.get('observed_at')),default=None),'record_count':len(allrows),'algorithms':sorted({r['algorithm_id'] for r in allrows}),'runs':sorted(runs),'metrics':METRICS,'selection':'历史最优组合：仅同问题/图/核数/冻结配置；不是单一算法的全量实验成绩。切换指标不会换赢家。'}
