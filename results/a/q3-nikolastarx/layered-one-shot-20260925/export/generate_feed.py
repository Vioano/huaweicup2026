#!/usr/bin/env python3
"""Export two retained R9 E0 diagnostics; read/hash only, never score."""
from __future__ import annotations
from copy import deepcopy
import gzip, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BASE = ROOT / 'results/a/q3-nikolastarx/layered-one-shot-20260925'
RUN = BASE / 'run'
SOURCE = 'e9ff04c3019dedadd5b2ff71ecfdd57ac1aabe4a'
REPO = 'huaweibei123/huaweicup2026'
BASELINE = ROOT / 'results/benchmark-board/official-singlecore-20260924/005/result.json.gz'
HERE = Path(__file__).resolve().parent


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    raw = p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix == '.gz' else raw)
def artifact(p): return {'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
def source(path, entry): return {'repo': REPO, 'commit': SOURCE, 'path': path, 'entrypoint': entry}
def require(test, why):
    if not test: raise ValueError(why)


def main():
    template = load(ROOT / 'results/a/q3-nikolastarx/query-flow-one-shot-20260925/export/feed.json')['records'][0]
    run, monitor = load(RUN/'run.json'), load(BASE/'resource-control/receipt.json')
    plan_path = BASE/'candidate/case_005_multicore_res.json'
    plan = load(plan_path)
    control = load(BASE/'control/control.json')
    p3, p2 = load(RUN/'p3.json.gz'), load(RUN/'p2.json.gz')
    w3, w2 = load(RUN/'p3.worker.json'), load(RUN/'p2.worker.json')
    baseline = load(BASELINE)
    identity = {'graph_sha256': control['identity']['graph_sha256'],
                'config_sha256': control['identity']['config_sha256'],
                'official_sha256': control['identity']['official_sha256'],
                'plan_sha256': sha(plan_path)}
    require(run['status']=='complete' and monitor['status']=='complete', 'run/supervisor incomplete')
    require(run['source_commit']==SOURCE and monitor['source_commit']==SOURCE, 'source commit drift')
    require(plan.keys()=={'node_to_subgraph','core_schedules'} and len(plan['core_schedules'])==5, 'plan structure')
    require(run['plan_sha256']==sha(plan_path) and monitor['command'][monitor['command'].index('--plan-sha256')+1]==sha(plan_path), 'plan SHA drift')
    require(control['identity']['graph_sha256']==run['source_input_sha256']['data/raw/a/official/data/case_005.json'], 'graph SHA drift')
    require(control['identity']['config_sha256']==run['source_input_sha256']['data/raw/a/official/data/config.txt'], 'config SHA drift')
    require(control['identity']['official_sha256']==run['official_code_sha256'], 'official SHA drift')
    require(sha(BASE/'control/control.json')==run['old_control']['control_sha256'], 'old control drift')
    require(sha(BASE/'resource-control/receipt.json') and len(run['phases'])==2 and {x['phase'] for x in run['phases']}=={'p3','p2'}, 'phase ledger')
    require(w3['status']==w2['status']=='complete' and w3['guard']['status']=='passed', 'worker/guard')
    require(all(w['result_sha256']==sha(RUN/f'{phase}.json.gz') for phase,w in (('p3',w3),('p2',w2))), 'result hash drift')
    require(p3['scene']==p2['scene']=='B' and p3['num_cores']==p2['num_cores']==5, 'result scene/cores')
    require(p3['makespan']==run['candidate_M3'] and p2['makespan']==run['candidate_M2'], 'result M drift')
    require(run['accepted'] is False and p3['makespan']<control['M3'] and p2['makespan']<control['M2']
            and p2['makespan']*control['M3']<control['M2']*p3['makespan'], 'acceptance control mismatch')
    require(sha(BASELINE)=='3efb00f0d7750733b54df72ce2acde81b6bbc510d92771f6414ff985864340a4'
            and baseline['scene']=='A' and baseline['num_cores']==1 and baseline['makespan']==95618, 'baseline identity')
    base_ref = {k:identity[k] for k in ('graph_sha256','config_sha256','official_sha256')}
    base_ref.update(route='E0',entrypoint='singlecore_evaluate.evaluate_singlecore',result=artifact(BASELINE))
    solver = source('src/q3/layered_query_flow.py','src.q3.layered_query_flow.construct_layered')
    runner = source('src/q3/layered_query_flow_probe.py','src.q3.layered_query_flow_probe.main')
    complete_refs = {'source_manifest':artifact(BASE/'proposal-manifest.json'),
        'admission':artifact(BASE/'P3_R9_005_K5_ADMISSION_20260925.json'),
        'actual_admitted_manifest':artifact(BASE/'P3_R9_005_K5_ADMITTED_MANIFEST_20260925.json'),
        'admission_decision':artifact(BASE/'P3_R9_005_K5_ADMISSION_DECISION_20260925.md'),
        'old_control':artifact(BASE/'control/control.json'),
        'plan':artifact(plan_path), 'p3_result':artifact(RUN/'p3.json.gz'),
        'p2_result':artifact(RUN/'p2.json.gz'), 'run':artifact(RUN/'run.json'),
        'p3_worker':artifact(RUN/'p3.worker.json'), 'p2_worker':artifact(RUN/'p2.worker.json'),
        'prepared':artifact(RUN/'prepared.json.gz'),
        'resource_receipt':artifact(BASE/'resource-control/receipt.json'),
        'resource_samples':artifact(BASE/'resource-control/samples.jsonl')}
    for phase in ('p3','p2'):
        for name in ('reservation.json','claim.json','stdout.txt','stderr.txt'):
            complete_refs[f'{phase}_{name.replace(".", "_")}']=artifact(RUN/f'{phase}.{name}')
    for name in ('stdout.txt','stderr.txt'):
        complete_refs[f'resource_{name.replace(".", "_")}']=artifact(BASE/'resource-control'/name)
    manifest_path=HERE/'evidence-manifest.json'
    if manifest_path.exists(): raise FileExistsError(manifest_path)
    manifest_path.write_text(json.dumps({'schema':'r9-005-export-evidence-v1','refs':complete_refs},indent=2)+'\n')
    def record(problem,phase,result,worker):
        rec=deepcopy(template)
        rec.update(attempt_id=f'nikolastarx-r9-layered-005-k5-{phase}', revision=1,
                   run_id='q3-r9-layered-005-one-shot-20260925T141831Z',
                   algorithm_id='q3-r9-layered-diagnostic', algorithm_name='Q3 R9 layered query-flow diagnostic',
                   variant='r9-layered-one-shot-fixed005-k5', solver_commit=SOURCE,
                   parameters={'requested_cores':5,'candidate_count':1,'plan_sha256':identity['plan_sha256'],
                               'selection':'one previously constructed fixed plan; P2 conditional on P3 guard and M3 threshold'},
                   problem=problem,case_id='005',cores=5,status='ok',runtime_id='macos-arm64-local-shared-48GiB',
                   observed_at=worker['finished_at'], identity=identity,
                   source_url=f'https://github.com/{REPO}/blob/{SOURCE}/src/q3/layered_query_flow.py')
        rec['metrics']={'makespan_cycles':result['makespan'],'solver_wall_seconds':None,
                        'evaluation_wall_seconds':worker['diagnostic_wall_seconds'],
                        'ddr_bytes':result['data_movement_bytes']['scheduled_copy_bytes'],
                        'extra_ddr_bytes':result['data_movement_bytes']['added_copy_bytes'],
                        'spill_bytes':result['data_movement_bytes']['spill_added_copy_bytes'],
                        'cache_hit_rate':result.get('cache_stats',{}).get('hit_rate') if phase=='p3' else None}
        rec['evaluator']={'route':'E0','commit':SOURCE,'entrypoint':
            'multicore_cut_evaluate_problem_3.evaluate_problem_3' if phase=='p3' else 'multicore_cut_evaluate_problem_2.evaluate_scene_b'}
        rec['artifacts']={'plan':artifact(plan_path),'result':artifact(RUN/f'{phase}.json.gz'),
            'run':artifact(RUN/'run.json'), 'trace':artifact(RUN/f'{phase}.worker.json'),
            'log':artifact(RUN/f'{phase}.stdout.txt'),'manifest':artifact(manifest_path)}
        rec['timing']={'solver_includes_evaluation':None,
            'evaluation_precision':'Worker diagnostic wall includes official E0 plus startup, profile observer, prepared capture and guard for P3; not E0-only.',
            'utc':'Original worker UTC timestamps; diagnostic wall measured by monotonic clock.'}
        p=rec['provenance']
        p['producer_session']='nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc'
        p['task_url']='https://github.com/huaweibei123/huaweicup2026/issues/51'
        p['solver']={'source':solver,'authors':['nikolastarx'],
            'method':'R9 layered query-flow fixed plan constructed before this isolated diagnostic; no integrated solver run or full-matrix claim.',
            'references':[],'upstream':[],'selected_algorithm_id':None,'selected_solver_commit':None}
        p['runner']={'source':runner,'argv':['python3','-B','-m','src.q3.layered_query_flow_probe',
            'results/a/q3-nikolastarx/layered-one-shot-20260925/candidate',
            'results/a/q3-nikolastarx/layered-one-shot-20260925/run','--source',SOURCE,
            '--plan-sha256',identity['plan_sha256'],'--admission-file','<redacted admission path>',
            '--admission-sha256',run['admission_sha256'],'--control',
            'results/a/q3-nikolastarx/layered-one-shot-20260925/control/control.json',
            '--control-sha256',run['old_control']['control_sha256']], 'working_directory':'.'}
        p['environment']={'os':run['environment']['platform'],'cpu':None,'gpu':'none',
            'ram_bytes':48*1024**3,'python':run['environment']['python'],
            'dependencies':'uv.lock sha256:'+run['source_input_sha256']['uv.lock'],
            'threads':None,'workers':1,'peak_rss_bytes':None}
        p['measurement']={'started_at':worker['started_at'],'finished_at':worker['finished_at'],
            'seed':None,'repeat_index':0,'cold_start':None,'solver_scope':None,
            'evaluation_scope':'One fixed-plan official E0 phase; reported worker diagnostic wall also includes wrapper/profiling, and P3 prepared capture and guard.',
            'budget':{'wall_seconds':600,'candidate_limit':1,'stop_reason':'One P3 and conditional same-plan P2 completed; zero retries; candidate rejected by G threshold.'},
            'calls':{'solver':0,'E0':1,'E1':0,'E2':0},
            'offline_costs':'Plan was constructed in a preceding static phase; no end-to-end cold solver time measured for this one-shot diagnostic.',
            'failure':None}
        p['missing_reasons']={
            'provenance.environment.cpu':f'CPU model absent from retained receipt ({run["environment"]["cpu_count"]} logical CPUs recorded).',
            'provenance.environment.threads':'Thread count not recorded.',
            'provenance.environment.peak_rss_bytes':'One-second supervisor sampling is not a hard process peak.',
            'provenance.measurement.seed':'Deterministic fixed plan; no random seed.',
            'provenance.measurement.cold_start':'Cold/warm state not recorded.',
            'provenance.measurement.solver_scope':'End-to-end constructor timing absent.'}
        rec['notes']=[
            'One case 005/K5 R9 layered diagnostic, not an integrated uniform solver or complete 500-cell run.',
            f'Official {problem} E0 result is complete and legal; run.accepted=false is a separate local two-metric gate: M3/M2 improved versus old, but P2/P3 cache gain declined.',
            'worker diagnostic_wall_seconds includes P3 prepared audit and must not be compared as isolated official evaluator latency or solver runtime.',
            'Guard step3_local_memory_peaks are prepared local Step3 values, not independently observed final multicore runtime peaks.',
            'The original plan, results, full run/worker/resource receipts, reservation/claim, prepared capture, and raw stdout/stderr remain cited unchanged.',
            'Official single-core baseline M=95618 is reused from the preexisting frozen E0 original; no baseline scoring in this export.',
            'No publication, board import, independent replay, or algorithm acceptance is claimed.',
            'R9 original Pro source: AI chats/20260925-Pro-P3-多层查询亲和/; local port, prepared guard, same-plan originals and one-shot receipts were checked here, not treated as a Pro-proven performance claim.']
        rec['baseline']=base_ref
        rec['cache_pair']=({k:identity[k] for k in ('graph_sha256','config_sha256','official_sha256','plan_sha256')}
            | {'cores':5,'route':'E0','result':artifact(RUN/'p2.json.gz')}) if phase=='p3' else None
        return rec
    feed={'schema_version':1,'submission_version':1,'records':[
        record('P3','p3',p3,w3),record('P2','p2',p2,w2)]}
    out=HERE/'board-feed-r9-005.json'
    if out.exists(): raise FileExistsError(out)
    out.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n')
    print(out.relative_to(ROOT),sha(out))

if __name__=='__main__': main()
