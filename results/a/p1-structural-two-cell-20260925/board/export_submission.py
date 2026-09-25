#!/usr/bin/env python3
"""Export the preserved 2026-09-25 two-cell structural P1 run to board-submission-v1.
Reads raw archived files under the sibling run-1056Z directory; writes only beside this file.
"""
from pathlib import Path
import gzip, hashlib, json

BOARD = Path(__file__).resolve().parent
ROOT = BOARD.parent
RUN = ROOT / 'run-1056Z'
RAW = RUN / 'raw' / 'workspace' / 'two-cell-run'
BASELINE = {
    'graph_sha256': '',
    'config_sha256': 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9',
    'official_sha256': 'de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0',
    'route': 'E0', 'entrypoint': 'singlecore_evaluate.evaluate_singlecore',
}
REPO = 'huaweibei123/huaweicup2026'
SOLVER_SHA = '3a1b82b71ca1ff6689eb8e72f17d26c48b52073c'
RUNNER_SHA = 'c44f0558c11f2f45030c8d1e1ea0ae51d9629e7c'
E0_SHA = 'a008dfb8f1b5b881844af312be0b7246b2c6b025'
RUN_ID = '20260925T1056Z-s6607-structural-two'


def digest(b): return hashlib.sha256(b).hexdigest()
def gzip_copy(src, dest):
    raw = src.read_bytes()
    with dest.open('wb') as f:
        with gzip.GzipFile(filename='', mode='wb', fileobj=f, mtime=0) as z: z.write(raw)
    return digest(dest.read_bytes())
def artifact(path):
    b=path.read_bytes(); return {'path':path.relative_to(ROOT.parent.parent.parent).as_posix(),'sha256':digest(b)}
def put_artifact(name, src, dest_name=None, compressed=False):
    dest=RUN / (dest_name or (src.name + ('.gz' if compressed else '')))
    dest.parent.mkdir(parents=True,exist_ok=True)
    if compressed: h=gzip_copy(src,dest)
    else:
        dest.write_bytes(src.read_bytes()); h=digest(dest.read_bytes())
    return {'path':dest.relative_to(ROOT.parent.parent.parent).as_posix(),'sha256':h}

records=[]
for case in ('016','024'):
    cell=RAW/case
    attempt=json.loads((RAW/'attempt.json').read_bytes())
    row=next(x for x in attempt['cells'] if x['case']==case)
    result_raw=(cell/'result.json').read_bytes(); result=json.loads(result_raw)
    plan=put_artifact('plan',cell/f'case_{case}_multicore_res.json',f'{case}/plan.json.gz',True)
    result_ref=put_artifact('result',cell/'result.json',f'{case}/result.json.gz',True)
    trace=put_artifact('trace',cell/'trace.json',f'{case}/trace.json.gz',True)
    log=put_artifact('log',cell/'official.log',f'{case}/official.log')
    solver_stdout=put_artifact('log',cell/'solver.stdout.raw.txt',f'{case}/solver.stdout.raw.txt')
    solver_stderr=put_artifact('log',cell/'solver.stderr.raw.txt',f'{case}/solver.stderr.raw.txt')
    e0_stdout=put_artifact('log',cell/'E0.stdout.raw.txt',f'{case}/E0.stdout.raw.txt')
    e0_stderr=put_artifact('log',cell/'E0.stderr.raw.txt',f'{case}/E0.stderr.raw.txt')
    plan_sha=plan['sha256']; graph=row['graph_sha256']
    baseline_path=RUN/f'baseline-{case}-singlecore.json.gz'
    baseline={**BASELINE,'graph_sha256':graph,'result':{'path':baseline_path.relative_to(ROOT.parent.parent.parent).as_posix(),'sha256':digest(baseline_path.read_bytes())}}
    # Per-cell public run receipt derives from the archived attempt row without changing its timings or calls.
    run_receipt={
      'kind':'board-run-cell-derived-from-preserved-remote-attempt','run_id':RUN_ID,'case_id':case,'cores':5,
      'derived_from':{'path':f'raw/workspace/two-cell-run/attempt.json','sha256':digest((RAW/'attempt.json').read_bytes())},
      'cell':row,'evaluator_result_sha256':digest(result_raw),
      'evaluator_result_fields':{'scene':result.get('scene'),'num_cores':result.get('num_cores'),'makespan':result.get('makespan'),'data_movement_bytes':result.get('data_movement_bytes')},
      'calls_total':attempt['calls'],'call_limits':attempt['maximum_calls'],
      'environment_limits':{'worker_limit':attempt['worker_limit'],'cpu':'not recorded','gpu':'not recorded','ram_bytes':'not recorded','os_release':'not recorded','aggregate_setup_peak_child_rss_kib':260360,'per_cell_peak_rss':'not recorded'},
      'notes':['Derived receipt points to exact archived attempt and result bytes. E1 was used for internal candidate selection; final reported result is independent E0.','The two successful cells are 2 of the 500 required P1 case/core cells; this is a partial run.']}
    run_path=RUN/f'{case}/run.json'; run_path.parent.mkdir(parents=True,exist_ok=True)
    run_path.write_text(json.dumps(run_receipt,ensure_ascii=False,indent=2)+'\n')
    run_ref={'path':run_path.relative_to(ROOT.parent.parent.parent).as_posix(),'sha256':digest(run_path.read_bytes())}
    start=row['solver']['started_at']; finish=row['solver']['finished_at']; ev=row['evaluation']
    missing={
      'provenance.environment.os':'VM OS release was not captured in the archived run evidence.',
      'provenance.environment.cpu':'CPU model/inventory was not captured.',
      'provenance.environment.gpu':'GPU inventory was not captured.',
      'provenance.environment.ram_bytes':'RAM size was not captured.',
      'provenance.environment.peak_rss_bytes':'Per-run peak RSS was not captured.',
      'provenance.measurement.seed':'The solver run did not record a random seed.',
      'provenance.measurement.cold_start':'OS file-cache state was not measured.'}
    rec={
      'attempt_id':f'nikolastarx-p1-structural-two-20260925-{case}-k5-r0','revision':1,'run_id':RUN_ID,
      'algorithm_id':'q1-structural-refine-experimental','algorithm_name':'P1 unified structural refinement solver',
      'variant':'variable-parent-then-intact-two-v1','solver_commit':SOLVER_SHA,
      'parameters':{'cores':5,'worker_limit':1,'E1_reserved_max':9,'actual_E1_calls':row['calls']['E1'],'solver_timeout_seconds':180,'E0_timeout_seconds':120,'retries':0},
      'problem':'P1','case_id':case,'cores':5,'status':'ok','runtime_id':'colab-linux-py3.12.13','observed_at':ev['finished_at'],
      'metrics':{'makespan_cycles':result['makespan'],'solver_wall_seconds':row['solver']['wall_seconds'],'evaluation_wall_seconds':ev['wall_seconds'],'ddr_bytes':result['data_movement_bytes']['scheduled_copy_bytes'],'extra_ddr_bytes':result['data_movement_bytes']['added_copy_bytes'],'spill_bytes':result['data_movement_bytes']['spill_added_copy_bytes']},
      'evaluator':{'route':'E0','commit':E0_SHA,'entrypoint':'multicore_cut_evaluate_problem_1.py -> contest_io.run_problem_cli(1)'},
      'identity':{'graph_sha256':graph,'config_sha256':BASELINE['config_sha256'],'official_sha256':BASELINE['official_sha256'],'plan_sha256':plan_sha},
      'artifacts':{'plan':plan,'result':result_ref,'run':run_ref,'trace':trace,'log':log},
      'timing':{'solver_includes_evaluation':False,'evaluation_precision':'Per-child monotonic wall timer in preserved attempt receipt.','utc':'UTC'},
      'provenance':{
       'producer_session':'nikolastarx/s-6607cb2735304751b36662035723372b','task_url':'https://github.com/huaweibei123/huaweicup2026/issues/98',
       'solver':{'source':{'repo':REPO,'commit':SOLVER_SHA,'path':'src/q1/structural_refine.py','entrypoint':'CLI: src/q1/structural_refine.py <graph> --cores 5 --output <plan> --diagnostics <json>'},'authors':['NikolaStarx'],'method':'The solver constructs a variable-parent candidate, then at most two intact candidates, and automatically selects among them using its candidate evaluation policy. Online E1 scores support selection; final metrics come from independent E0.','references':['https://github.com/huaweibei123/huaweicup2026/blob/3a1b82b71ca1ff6689eb8e72f17d26c48b52073c/src/q1/intact_frontier.py'],'upstream':[{'repo':REPO,'commit':'3a1b82b71ca1ff6689eb8e72f17d26c48b52073c','path':'src/q1/intact_frontier.py','entrypoint':'intact frontier mechanism; module documentation records Fang Stage K/H/J origins'}],'selected_algorithm_id':'q1-intact-frontier-research','selected_solver_commit':SOLVER_SHA},
       'runner':{'source':{'repo':REPO,'commit':RUNNER_SHA,'path':'src/review/p1_structural_two_cell_once.py','entrypoint':'main'},'argv':['.venv/bin/python','-B','-m','src.review.p1_structural_two_cell_once','--output-root','/content/p1_structural_two_cell/workspace/two-cell-run','--deadline-monotonic','980.077550085'],'working_directory':'.'},
       'environment':{'os':None,'cpu':None,'gpu':None,'ram_bytes':None,'python':'3.12.13','dependencies':'uv sync --locked succeeded; exact installed dependency inventory not recorded.','threads':1,'workers':1,'peak_rss_bytes':None},
       'measurement':{'started_at':start,'finished_at':ev['finished_at'],'seed':None,'repeat_index':0,'cold_start':None,'solver_scope':'Fresh solver process from launch through plan output and process cleanup; excludes subsequent E0. OS cache state is unknown.','evaluation_scope':'One independent official E0 child process on the selected fixed plan, through output, exit and cleanup. E1 candidate scoring occurred online and is reflected in the solver wall.','budget':{'wall_seconds':180,'candidate_limit':9,'stop_reason':'One solver and one E0 completed successfully; no retry.'},'calls':{'solver':1,'E0':1,'E1':row['calls']['E1'],'E2':0},'offline_costs':'Source/input capsule packaging and locked-dependency setup occurred outside solver wall. No offline training or current-case preoptimization occurred in this run.','failure':None},'missing_reasons':missing},
      'source_url':'https://github.com/huaweibei123/huaweicup2026/pull/170','notes':['One of two successful cells in a partial 2/500 run; does not establish a full-matrix result.','E1 scoring contributed to online plan selection; the final reported metrics come from the independent E0 output.','The intact-frontier module documents its Fang Stage K/H/J origins; no acceptance claim is made.','Raw archive and complete extracted files are preserved under results/a/p1-structural-two-cell-20260925/run-1056Z/raw/.'],
      'baseline':baseline}
    records.append(rec)
feed={'schema_version':1,'submission_version':1,'records':records}
path=BOARD/'board-feed-20260925T1056Z-structural-two.json'
path.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n')
print(path)
