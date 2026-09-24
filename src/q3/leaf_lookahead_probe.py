"""Four fixed owner controls, one leaf lookahead; at most eight new E0 calls."""
import argparse
from pathlib import Path
import subprocess
import sys
import time

from .construct import ROOT, Index
from .feedback_benchmark import digest, git_bytes, read, utc, verify_source, write
from .leaf_lookahead import transform
from .safe_solve import encoded

FOREST_COMMIT = 'bff88a66cd76ceb2d75242bf99d34bfe8b1879d4'
BAND_COMMIT = '27409658d869671d30e940f536bbab30d50d3ef9'
BAND_RUN = 'results/a/q3-nikolastarx/band-mechanism-20260925/run.json'
BUDGET = {'new_p3': 4, 'new_p2_max': 4, 'workers': 1, 'retries': 0,
          'solver_calls': 0, 'per_call_seconds': 90, 'whole_batch_seconds': 360}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('output', type=Path)
    p.add_argument('--source', required=True)
    p.add_argument('--forest-root', required=True, type=Path)
    p.add_argument('--preflight', action='store_true')
    args = p.parse_args()
    start = time.monotonic()
    official, hashes = verify_source(args.source, {'058', '079'})
    assert (ROOT / BAND_RUN).read_bytes() == git_bytes(ROOT, BAND_COMMIT, BAND_RUN)
    band = read(ROOT / BAND_RUN)
    coverage = read(ROOT / 'results/a/q3-nikolastarx/reuse-coverage-20260925/coordinates.json')
    proposals = []
    for case in ('058', '079'):
        index = Index(read(ROOT / f'data/raw/a/official/data/case_{case}.json'))
        for variant in ('forest', 'band_pair'):
            if variant == 'forest':
                ref = next(r for r in coverage if r['case']==int(case) and r['cores']==5)
                receipt_path = Path(ref['receipt_path'])
                assert (args.forest_root / receipt_path).read_bytes() == git_bytes(args.forest_root, FOREST_COMMIT, str(receipt_path))
                receipt = read(args.forest_root / receipt_path)
                plan_path = args.forest_root / receipt_path.parent.parent / f'case_{case}_multicore_res.json'
                result_path = args.forest_root / receipt_path.parent / 'result.json.gz'
                ph, rh = receipt['plan_sha256'], receipt['result_sha256']
            else:
                ref = next(r for r in band['plans'] if r['case_id']==case and r['order_mode']=='pair_cache_model')
                result = next(r for r in band['results'] if r['case_id']==case and r['order_mode']=='pair_cache_model' and r['problem']==3)
                plan_path, result_path = ROOT / ref['plan_path'], ROOT / result['result_path']
                ph, rh = ref['plan_sha256'], result['result_sha256']
            assert digest(plan_path)==ph and digest(result_path)==rh
            before = time.monotonic()
            plan, metadata = transform(index, read(plan_path))
            proposals.append({'case_id':case,'variant':variant,'raw':encoded(plan),'metadata':metadata,
                              'construct_seconds':time.monotonic()-before,'baseline_plan_sha256':ph,
                              'baseline_result_sha256':rh,'baseline_makespan':read(result_path)['makespan']})
    if args.preflight:
        print({'valid':True,'plans':len(proposals),'new_e0':0,'seconds':time.monotonic()-start})
        return
    out = args.output.resolve()
    out.relative_to(ROOT / 'results/a/q3-nikolastarx')
    out.mkdir(parents=True, exist_ok=False)
    state = {'status':'running','started_at':utc(),'source_commit':args.source,'budget':BUDGET,
             'official_code_sha256':official,'source_input_sha256':hashes,'plans':[],'evaluations':[],
             'new_p3':0,'new_p2':0,
             'scope':'4 offline transformed controls, same owners and compute pipe words; not solver/full500'}

    def save():
        state['elapsed_seconds']=time.monotonic()-start
        write(out/'run.json',state)

    save()
    try:
        for proposal in proposals:
            folder=out/f"{proposal['case_id']}-{proposal['variant']}"
            folder.mkdir()
            plan_path=folder/'plan.json'
            plan_path.write_bytes(proposal.pop('raw'))
            proposal.update(plan_path=str(plan_path.relative_to(ROOT)),plan_sha256=digest(plan_path))
            state['plans'].append(proposal)
        save()
        for proposal in state['plans']:
            folder=ROOT / Path(proposal['plan_path']).parent
            for problem in (3,2):
                # A P2 pair is acquired only for a P3 improvement over that exact owner control.
                if problem==2 and proposal['new_makespan']>=proposal['baseline_makespan']:
                    proposal['p2_pair_status']='not_run_p3_did_not_improve'
                    save()
                    continue
                remaining=BUDGET['whole_batch_seconds']-(time.monotonic()-start)
                if remaining<=0 or state[f'new_p{problem}']>=4:
                    raise TimeoutError('frozen lookahead probe budget reached')
                result_path=folder/f'p{problem}.json.gz'
                command=['-m','src.q3.oracle',f"data/raw/a/official/data/case_{proposal['case_id']}.json",
                         proposal['plan_path'],str(problem),str(result_path.relative_to(ROOT))]
                record={'case_id':proposal['case_id'],'variant':proposal['variant'],'problem':problem,
                        'status':'reserved','plan_sha256':proposal['plan_sha256'],'command':['python',*command]}
                state['evaluations'].append(record)
                state[f'new_p{problem}']+=1
                save()
                before=time.monotonic()
                with (folder/f'p{problem}.stdout.txt').open('xb') as stdout,(folder/f'p{problem}.stderr.txt').open('xb') as stderr:
                    subprocess.run([sys.executable,*command],cwd=ROOT,stdout=stdout,stderr=stderr,
                                   timeout=min(BUDGET['per_call_seconds'],remaining),check=True)
                external_wall=time.monotonic()-before
                result=read(result_path)
                assert result['num_cores']==5 and digest(ROOT/proposal['plan_path'])==proposal['plan_sha256']
                if problem==3:
                    assert result.get('problem')==3
                else:
                    assert 'cache_stats' not in result
                record.update(status='ok',makespan=result['makespan'],result_path=str(result_path.relative_to(ROOT)),
                              result_sha256=digest(result_path),external_e0_seconds=external_wall,
                              movement=result['data_movement_bytes'],cache_stats=result.get('cache_stats'))
                if problem==3:
                    proposal['new_makespan']=result['makespan']
                else:
                    proposal['p2_pair_status']='measured'
                save()
        assert all(digest(ROOT/path)==sha for path,sha in hashes.items())
        state['status']='complete'
    except Exception as error:
        state.update(status='stopped_on_failure',error=f'{type(error).__name__}: {error}')
        raise
    finally:
        state['finished_at']=utc()
        save()
    print({k:state[k] for k in ('status','new_p3','new_p2','elapsed_seconds')})


if __name__=='__main__':
    main()
