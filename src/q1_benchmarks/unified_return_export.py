"""Export the completed three-cell unified return smoke without scoring or rerunning."""
from __future__ import annotations
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'results/a/q1-unified-return-smoke-20260925/20260924T1844Z-return3'
OUT = RUN / 'board-export'
BASELINE_COMMIT = '6fcec11ccc472a1a652b21feb6fccf85a4555598'
REPO = 'huaweibei123/huaweicup2026'

def digest(raw): return hashlib.sha256(raw).hexdigest()
def rel(path): return path.relative_to(ROOT).as_posix()
def ref(path): return {'path':rel(path), 'sha256':digest(path.read_bytes())}
def dump(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def git_blob(path): return subprocess.check_output(['git','show',f'{BASELINE_COMMIT}:{path}'],cwd=ROOT)
def source(commit,path,entry): return {'repo':REPO,'commit':commit,'path':path,'entrypoint':entry}

def main():
    batch=json.loads((RUN/'batch.json').read_text())
    assert batch['status']=='complete' and batch['cleanup_confirmed'] and batch['failure'] is None
    assert batch['calls']=={'solver':3,'external_E0':3,'internal_E1_confirmed':9,'internal_E1_upper_bound':9,'E2':0,'retries':0}
    assert not OUT.exists()
    OUT.mkdir()
    records=[]; receipt=[]
    for case in ('008','084','095'):
        cell=RUN/'cells'/case/'k5'; run=json.loads((cell/'run.json').read_text()); result=json.loads((cell/'result.json').read_text()); diag=json.loads((cell/'diagnostics.json').read_text())
        assert run['status']=='ok' and run['case_id']==case and run['cores']==5
        assert run['consistency']['status']=='equal' and run['consistency']['makespan']==result['makespan']
        assert run['consistency']['data_movement_bytes']==result['data_movement_bytes']
        assert run['online_ledger']['exact'] and run['online_ledger']['actual_e1_calls']==diag['actual_e1_calls']
        assert run['selected']==diag['selected']
        for name, info in run['artifacts'].items(): assert digest((ROOT/info['path']).read_bytes())==info['sha256']
        base=f'results/benchmark-board/official-singlecore-20260924/{case}'
        baseline_run_raw=git_blob(base+'/run.json'); baseline_run=json.loads(baseline_run_raw)
        baseline_result_raw=git_blob(base+'/result.json.gz'); baseline_result=json.loads(gzip.decompress(baseline_result_raw))
        assert baseline_run['status']=='ok' and baseline_run['entrypoint']=='singlecore_evaluate.evaluate_singlecore'
        assert baseline_result['scene']=='A' and baseline_result['num_cores']==1
        assert baseline_result['makespan']==baseline_run['makespan_cycles']
        assert digest(baseline_result_raw)==baseline_run['artifacts']['result.json']['sha256']
        identity={'graph_sha256':run['graph_sha256'],'config_sha256':batch['config_sha256'],'official_sha256':batch['official_code_hash'],'plan_sha256':run['artifacts']['plan.json']['sha256']}
        assert identity['graph_sha256']==baseline_run['graph_sha256']
        assert identity['config_sha256']==baseline_run['config_sha256']
        assert identity['official_sha256']==baseline_run['official_code_hash']
        target=OUT/case; target.mkdir()
        (target/'plan.json').write_bytes((cell/'plan.json').read_bytes())
        (target/'result.json.gz').write_bytes(gzip.compress((cell/'result.json').read_bytes(),mtime=0))
        (target/'trace.json.gz').write_bytes(gzip.compress((cell/'trace.json').read_bytes(),mtime=0))
        # The original run receipt contains absolute personal and temporary paths. Keep
        # its hash and a derived path-neutral copy; never claim this is the raw byte stream.
        safe_run=json.loads((cell/'run.json').read_text())
        for process in ('solver','evaluation'):
            argv=safe_run[process]['argv']
            safe_run[process]['argv']=['<local-python>' if x.endswith('/.venv/bin/python') else '<local-path>' if x.startswith('/') else x for x in argv]
        for item in safe_run['artifacts'].values(): item['path']=item['path'].removeprefix('results/a/q1-unified-return-smoke-20260925/20260924T1844Z-return3/')
        safe_run['derivation']={'original_sha256':digest((cell/'run.json').read_bytes()),'change':'Absolute argv paths replaced with local-path tokens; artifact paths made relative to original batch. Original receipt remains in local batch directory.'}
        dump(target/'run-derived.json',safe_run)
        (target/'baseline-result.json.gz').write_bytes(baseline_result_raw)
        (target/'baseline-run.json').write_bytes(baseline_run_raw)
        artifacts={'plan':ref(target/'plan.json'),'result':ref(target/'result.json.gz'),'run':ref(target/'run-derived.json'),'trace':ref(target/'trace.json.gz')}
        move=result['data_movement_bytes']
        missing={'provenance.environment.threads':'Batch did not measure runtime thread count','provenance.environment.peak_rss_bytes':'Only sampled process-group RSS, no isolated continuous peak','provenance.measurement.seed':'Deterministic runner; no seed recorded','provenance.measurement.cold_start':'Fresh subprocess but OS page cache not flushed','provenance.measurement.offline_costs':'Offline preparation cost not quantified by this smoke batch'}
        record={
          'attempt_id':f'nikolastarx-{batch["run_id"]}-P1-{case}-k5-r0','revision':1,'run_id':batch['run_id'],
          'algorithm_id':diag['algorithm_id'],'algorithm_name':'P1 统一结构守卫求解器','variant':diag['variant'],
          'solver_commit':batch['source_commit'],'problem':'P1','case_id':case,'cores':5,'status':'ok',
          'parameters':{'selected':run['selected'],'candidate_limit':5,'internal_E1_timeout_seconds':60,'solver_timeout_seconds':300,'external_E0_timeout_seconds':180,'workers':1,'retries':0,'stop_reason':diag['stop_reason']},
          'metrics':{'makespan_cycles':result['makespan'],'solver_wall_seconds':run['solver']['wall_seconds'],'evaluation_wall_seconds':run['evaluation']['wall_seconds'],'ddr_bytes':move['scheduled_copy_bytes'],'extra_ddr_bytes':move['added_copy_bytes'],'spill_bytes':move['spill_added_copy_bytes']},
          'evaluator':{'route':'E0','commit':batch['source_commit'],'entrypoint':'multicore_cut_evaluate_problem_1.evaluate_scene_a'},
          'identity':identity,'artifacts':artifacts,'runtime_id':'nikolastarx-m5pro-macos-py312-20260924','observed_at':run['finished_at'],
          'timing':{'solver_includes_evaluation':False,'evaluation_precision':'time.perf_counter elapsed seconds','utc':'Original subprocess timestamps are UTC; solver wall includes internal E1, external E0 separate'},
          'provenance':{'producer_session':'nikolastarx/s-6607cb2735304751b36662035723372b','task_url':'https://github.com/huaweibei123/huaweicup2026/issues/33',
            'solver':{'source':source(batch['source_commit'],'src/q1/unified.py','main'),'authors':['nikolastarx'],'method':'Structural features select and E1-rank up to five direct P1 plans; final external E0 checks selected plan.','references':[],'upstream':[],'selected_algorithm_id':run['selected'],'selected_solver_commit':batch['source_commit']},
            'runner':{'source':source(batch['runner_commit'],'src/q1_benchmarks/unified_return_smoke.py','main'),'argv':[],'working_directory':'.'},
            'environment':{**batch['environment'],'peak_rss_bytes':None},
            'measurement':{'started_at':run['started_at'],'finished_at':run['finished_at'],'seed':None,'repeat_index':0,'cold_start':None,
              'solver_scope':'Full child process startup, graph input, construction, online E1 ranking, plan and diagnostics output through exit; OS caches not flushed.',
              'evaluation_scope':'Independent external unmodified official E0 child process through result/trace/log output and exit.',
              'budget':{'wall_seconds':300,'candidate_limit':5,'stop_reason':diag['stop_reason']},
              'calls':{'solver':1,'E0':1,'E1':run['online_ledger']['actual_e1_calls'],'E2':0},'offline_costs':None,'failure':None},'missing_reasons':missing},
          'notes':['Only three P1 k5 cells of the 500-cell P1 matrix; v2 partial preview, not a full-matrix or mixed-v1 score.',
                   'All E1 winner and external E0 Makespan/movement fields matched exactly. Runner launcher argv was not retained in batch receipt; runner.argv is empty and must not be interpreted as a zero-argument run.',
                   f'Original local run receipt SHA256={safe_run["derivation"]["original_sha256"]}; committed run is path-redacted derivative.',
                   f'Original result SHA256={digest((cell/"result.json").read_bytes())}; committed gzip is byte-preserving decompression derivative.',
                   f'Official singlecore denominator from {BASELINE_COMMIT}:{base}/result.json.gz; no baseline rerun.'],
          'source_url':'https://github.com/huaweibei123/huaweicup2026/issues/33',
          'baseline':{'graph_sha256':identity['graph_sha256'],'config_sha256':identity['config_sha256'],'official_sha256':identity['official_sha256'],'route':'E0','entrypoint':'singlecore_evaluate.evaluate_singlecore','result':ref(target/'baseline-result.json.gz')}
        }
        records.append(record)
        receipt.append({'case':case,'makespan':result['makespan'],'selected':run['selected'],'solver_wall_seconds':run['solver']['wall_seconds'],'external_E0_wall_seconds':run['evaluation']['wall_seconds'],'internal_E1_calls':run['online_ledger']['actual_e1_calls'],'baseline':baseline_result['makespan'],'original_run_sha256':digest((cell/'run.json').read_bytes()),'original_result_sha256':digest((cell/'result.json').read_bytes()),'original_trace_sha256':digest((cell/'trace.json').read_bytes()),'trace_archive':ref(target/'trace.json.gz')})
    feed=OUT/'board-feed-20260924T1844Z-return3.json';dump(feed,{'schema_version':1,'submission_version':1,'records':records})
    dump(OUT/'export-receipt.json',{'source_commit':batch['source_commit'],'runner_commit':batch['runner_commit'],'baseline_source_commit':BASELINE_COMMIT,'feed':ref(feed),'records':receipt,'new_calls':{'solver':0,'E0':0,'E1':0,'E2':0}})
    print(rel(feed),digest(feed.read_bytes()))
if __name__=='__main__':main()
