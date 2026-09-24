"""Export four-cell P1 v4 development probe to submission-v1 without scoring."""
from __future__ import annotations
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
RUN_ID='20260924T1916Z-s59ee'
CELLS=[('039',4),('080',4),('084',5),('008',5)]
CASES=sorted({c for c,k in CELLS})
RUN=ROOT/'output/p1-v4-pilot-s59ee'/RUN_ID
OUT=ROOT/'results/a/q1-v4-pilot-20260925-s59'/RUN_ID
BASELINE_COMMIT='6fcec11ccc472a1a652b21feb6fccf85a4555598'
REPO='huaweibei123/huaweicup2026'
SESSION='nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc'
SOURCE='a0537aeb72dc702af86d67d3194587d581ac207c'
RUNNER='daeecb7217eacb5a825e9cf070d06a50fd03203c'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def ref(p):return {'path':rel(p),'sha256':sha(p.read_bytes())}
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def blob(commit,path):return subprocess.check_output(['git','show',f'{commit}:{path}'],cwd=ROOT)
def source(commit,path,entry):return {'repo':REPO,'commit':commit,'path':path,'entrypoint':entry}
def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,str):
        return value.replace(str(ROOT),'.').replace('/Users/nikolastar/Projects/huaweicup2026/.venv/bin/python','<local-python>').replace('/private/var/folders/','<temp-root>/').replace('/var/folders/','<temp-root>/')
    return value

def main():
    batch=json.loads((RUN/'batch.json').read_text())
    assert batch['status']=='complete' and batch['cleanup_confirmed'] and batch['status_counts']=={'ok':4},batch
    assert batch['source_commit']==SOURCE and batch['runner_commit']==RUNNER
    assert not OUT.exists()
    OUT.mkdir(parents=True)
    (OUT/'baseline').mkdir()
    baselines={}
    for c in CASES:
        base=f'results/benchmark-board/official-singlecore-20260924/{c}'
        base_run_raw=blob(BASELINE_COMMIT,base+'/run.json')
        base_result_raw=blob(BASELINE_COMMIT,base+'/result.json.gz')
        base_run=json.loads(base_run_raw); base_result=json.loads(gzip.decompress(base_result_raw))
        assert base_run['status']=='ok' and base_run['entrypoint']=='singlecore_evaluate.evaluate_singlecore'
        assert base_result['scene']=='A' and base_result['num_cores']==1 and base_result['makespan']==base_run['makespan_cycles']
        assert sha(base_result_raw)==base_run['artifacts']['result.json']['sha256']
        target=OUT/'baseline'/c; target.mkdir()
        (target/'result.json.gz').write_bytes(base_result_raw)
        (target/'run.json').write_bytes(base_run_raw)
        baselines[c]=(base_run,base_result,ref(target/'result.json.gz'))
    records=[]; receipt=[]
    for c,k in CELLS:
        cell=RUN/'cells'/c/f'k{k}'
        row=json.loads((cell/'run.json').read_text())
        assert row['status']=='ok' and row['case_id']==c and row['cores']==k
        assert row['calls']['solver']==row['calls']['external_E0']==1 and row['calls']['internal_E1']<=6
        assert row['solver']['cleanup_confirmed'] and row['evaluation']['cleanup_confirmed']
        assert row['online_ledger']['exact'] and row['online_ledger']['actual_e1_calls']==row['calls']['internal_E1']
        result=json.loads((cell/'result.json').read_text()); diag=json.loads((cell/'diagnostics.json').read_text())
        assert result['scene']=='A' and result['num_cores']==k and result['makespan']==row['makespan_cycles']
        assert result['data_movement_bytes']==row['data_movement_bytes']
        assert diag['algorithm_id']=='q1-unified-structural-guard' and diag['selected']==row['selected']
        if row['consistency']['status']=='equal':
            assert row['consistency']['makespan']==result['makespan'] and row['consistency']['data_movement_bytes']==result['data_movement_bytes']
        elif row['consistency']['status']=='not_applicable':
            assert diag['stop_reason']=='single-distinct-plan' and row['calls']['internal_E1']==0
        else:
            assert row['consistency']['status']=='internal-score-failure' and diag['stop_reason']=='first-score-failure'
            selected_success=[x for x in diag['online_scores'] if x['name']==diag['selected'] and x['status']=='ok']
            assert len(selected_success)<=1
            if selected_success:
                assert selected_success[0]['makespan']==result['makespan']
                assert selected_success[0]['data_movement_bytes']==result['data_movement_bytes']
        for info in row['artifacts'].values(): assert sha((ROOT/info['path']).read_bytes())==info['sha256']
        base_run,base_result,base_ref=baselines[c]
        identity={'graph_sha256':row['graph_sha256'],'config_sha256':batch['config_sha256'],'official_sha256':batch['official_code_hash'],'plan_sha256':row['artifacts']['plan.json']['sha256']}
        assert identity['graph_sha256']==base_run['graph_sha256']
        assert identity['config_sha256']==base_run['config_sha256']
        assert identity['official_sha256']==base_run['official_code_hash']
        target=OUT/'cells'/c/f'k{k}'; target.mkdir(parents=True)
        (target/'plan.json').write_bytes((cell/'plan.json').read_bytes())
        (target/'result.json.gz').write_bytes(gzip.compress((cell/'result.json').read_bytes(),mtime=0))
        (target/'trace.json.gz').write_bytes(gzip.compress((cell/'trace.json').read_bytes(),compresslevel=1,mtime=0))
        safe=clean(row)
        for stage in ('solver','evaluation'):
            safe[stage]['user_cpu_seconds']=None
            safe[stage]['system_cpu_seconds']=None
            safe[stage]['cpu_scope']='Concurrent RUSAGE_CHILDREN overlaps other cells and is not attributable per cell; original values deliberately omitted. Wall time remains per process.'
        safe['derivation']={'original_local_run_sha256':sha((cell/'run.json').read_bytes()),'change':'Absolute workspace and temporary paths replaced; global child CPU counters blanked because concurrent cells overlap. Original remains in local output directory.'}
        dump(target/'run-derived.json',safe)
        artifacts={'plan':ref(target/'plan.json'),'result':ref(target/'result.json.gz'),'run':ref(target/'run-derived.json')}
        move=result['data_movement_bytes']
        missing={'provenance.environment.threads':'Batch did not measure internal runtime thread count',
                 'provenance.measurement.seed':'Deterministic solver; no seed recorded',
                 'provenance.measurement.offline_costs':'Offline build/cache preparation not separately quantified'}
        record={
          'attempt_id':f'nikolastarx-{RUN_ID}-P1-{c}-k{k}-r0','revision':1,'run_id':RUN_ID,
          'algorithm_id':diag['algorithm_id'],'algorithm_name':'P1 统一结构守卫求解器','variant':diag['variant'],
          'solver_commit':SOURCE,'problem':'P1','case_id':c,'cores':k,'status':'ok',
          'parameters':{'selected':row['selected'],'candidate_limit':6,'internal_E1_timeout_seconds':60,
              'solver_timeout_seconds':300,'external_E0_timeout_seconds':180,'batch_workers_max':1,
              'retries':0,'stop_reason':diag['stop_reason'],'routing':'fixed structural features from source; no case ID or history lookup'},
          'metrics':{'makespan_cycles':result['makespan'],'solver_wall_seconds':row['solver']['wall_seconds'],
              'evaluation_wall_seconds':row['evaluation']['wall_seconds'],'ddr_bytes':move['scheduled_copy_bytes'],
              'extra_ddr_bytes':move['added_copy_bytes'],'spill_bytes':move['spill_added_copy_bytes']},
          'evaluator':{'route':'E0','commit':SOURCE,'entrypoint':'multicore_cut_evaluate_problem_1.evaluate_scene_a'},
          'identity':identity,'artifacts':artifacts,'runtime_id':'nikolastarx-m5pro-macos-py312-20260924',
          'observed_at':row['finished_at'],
          'timing':{'solver_includes_evaluation':False,'evaluation_precision':'time.perf_counter elapsed seconds',
              'utc':'Solver wall includes online E1; independent external E0 is separate.'},
          'provenance':{'producer_session':SESSION,'task_url':'https://github.com/huaweibei123/huaweicup2026/issues/33',
            'solver':{'source':source(SOURCE,'src/q1/unified.py','main'),'authors':['nikolastarx'],
              'method':'Fixed structural features construct up to six distinct P1 plans; online E1 ranks them, with specified failure fallback; independent official E0 accepts final plan.',
              'references':[],'upstream':[],'selected_algorithm_id':row['selected'],'selected_solver_commit':SOURCE},
            'runner':{'source':source(RUNNER,'src/q1_benchmarks/s59ee_v4_pilot.py','run'),
              'argv':['<local-python>','-B','src/q1_benchmarks/s59ee_v4_pilot.py',RUN_ID],'working_directory':'.'},
            'environment':{**batch['environment'],'workers':1,'peak_rss_bytes':row['solver']['sampled_peak_group_rss_bytes']},
            'measurement':{'started_at':row['started_at'],'finished_at':row['finished_at'],'seed':None,
              'repeat_index':0,'cold_start':False,
              'solver_scope':'Fresh child interpreter, input read, construction, all online E1, plan and diagnostics output through exit; OS caches not flushed.',
              'evaluation_scope':'Independent unmodified official E0 child through result, trace and log output.',
              'budget':{'wall_seconds':300,'candidate_limit':6,'stop_reason':diag['stop_reason']},
              'calls':{'solver':1,'E0':1,'E1':row['calls']['internal_E1'],'E2':0},
              'offline_costs':None,'failure':None},'missing_reasons':missing},
          'notes':['Four-cell bounded P1 v4 development probe; not a complete batch and not eligible for a per-core full score.',
                   'Independent official E0 result; internal E1 winner consistency is recorded when online ranking succeeded.',
                   'Concurrent global child CPU counters cannot be attributed to individual cells and are omitted from the public receipt; per-process wall times remain valid.',
                   f'Local original run SHA256={safe["derivation"]["original_local_run_sha256"]}; public run is redacted derivative.',
                   f'Original result SHA256={sha((cell/"result.json").read_bytes())}; public gzip decompresses to identical bytes.',
                   f'Trace gzip SHA256={ref(target/"trace.json.gz")["sha256"]}; independent E0 log retained locally.',
                   f'Official singlecore denominator fixed at {BASELINE_COMMIT}:results/benchmark-board/official-singlecore-20260924/{c}/result.json.gz; no baseline rerun.'],
          'source_url':'https://github.com/huaweibei123/huaweicup2026/issues/33',
          'baseline':{'graph_sha256':identity['graph_sha256'],'config_sha256':identity['config_sha256'],
              'official_sha256':identity['official_sha256'],'route':'E0','entrypoint':'singlecore_evaluate.evaluate_singlecore','result':base_ref}
        }
        records.append(record)
        receipt.append({'case':c,'cores':k,'makespan':result['makespan'],'selected':row['selected'],
                        'solver_wall_seconds':row['solver']['wall_seconds'],'external_E0_wall_seconds':row['evaluation']['wall_seconds'],
                        'internal_E1_calls':row['calls']['internal_E1'],'baseline':base_result['makespan'],
                        'trace_sha256':sha((cell/'trace.json').read_bytes())})
    feed=OUT/'board-feed-4.json';dump(feed,{'schema_version':1,'submission_version':1,'records':records})
    dump(OUT/'export-receipt.json',{'source_commit':SOURCE,'runner_commit':RUNNER,'baseline_source_commit':BASELINE_COMMIT,
         'feed':ref(feed),'records':receipt,'new_calls':{'solver':0,'E0':0,'E1':0,'E2':0}})
    speedups={f"{r['case_id']}-k{r['cores']}":baselines[r['case_id']][1]['makespan']/r['metrics']['makespan_cycles'] for r in records}
    print(json.dumps({'feed':rel(feed),'sha256':sha(feed.read_bytes()),'records':len(records),'preview_speedups':speedups},ensure_ascii=False))
if __name__=='__main__':main()
