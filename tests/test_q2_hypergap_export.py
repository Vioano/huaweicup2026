"""Offline compact-summary contract fixture; never starts a solver or evaluator."""
from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import q2_hypergap_export as ex


def fixture(root):
    manifest_path = ex.ROOT / 'results/a/q2-nikolastarx/hypergap-full500-20260925/manifest-workers1.json'
    manifest = ex.read(manifest_path)
    old = ex.read(ex.ROOT / manifest['baseline_manifest']['path'])
    sources = {Path(p).name: h for p, h in manifest['solver_sources'].items()}
    sources['hypergap_full500.py'] = ex.sha(subprocess.check_output(
        ['git', 'show', ex.RUNNER+':src/q2_nikolastarx/hypergap_full500.py'], cwd=ex.ROOT))
    rows = []
    for spec in old['rows'][:5]:
        case, cores = spec['case'], spec['cores']
        cell = root / f'{case}-k{cores}'
        (cell/'online').mkdir(parents=True)
        (cell/'solver-process').mkdir()
        (cell/'e0-process').mkdir()
        plan = subprocess.check_output(['git', 'show', spec['baseline_plan']['commit']+':'+spec['baseline_plan']['path']], cwd=ex.ROOT)
        truth = subprocess.check_output(['git', 'show', spec['baseline_truth']['commit']+':'+spec['baseline_truth']['path']], cwd=ex.ROOT)
        result = json.loads(gzip.decompress(truth))
        result_raw = ex.jbytes(result)
        (cell/'plan.json').write_bytes(plan)
        (cell/'result.json').write_bytes(result_raw)
        process = {'status':'ok','wall_seconds':0.2,'observed_peak_rss_bytes':1000,
                   'started_at':'2026-09-25T00:00:00Z','finished_at':'2026-09-25T00:00:01Z',
                   'argv':['synthetic-solver'], 'surviving_pids':[]}
        e0 = {**process, 'wall_seconds':0.1, 'argv':['synthetic-e0']}
        (cell/'solver-process/process.json').write_bytes(ex.jbytes(process))
        (cell/'e0-process/process.json').write_bytes(ex.jbytes(e0))
        ledger = {'status':'ok','request_in_flight':False,
                  'solver_checkout_commit':ex.RUNNER,'graph_sha256':spec['graph']['sha256'],
                  'config_sha256':old['config']['sha256'],'cores':cores,
                  'plan_sha256':ex.sha(plan),'solver_source_sha256':sources,
                  'calls':{'E2_api_attempted':0,'native_returns':0,'E0_fallback':0},
                  'possible_E0_fallback_calls':0,'attempts':[],
                  'runtime':{'platform':'fixture','python':'fixture'}}
        ledger_raw = ex.jbytes(ledger)
        (cell/'online/solver.json').write_bytes(ledger_raw)
        row = {'case':case,'cores':cores,'status':'accepted',
               'paths':{'folder':cell.name,'plan':f'{cell.name}/plan.json',
                        'solver_ledger':f'{cell.name}/online/solver.json',
                        'result':f'{cell.name}/result.json',
                        'trace':f'{cell.name}/trace.json','log':f'{cell.name}/official.log'},
               'plan_sha256':ex.sha(plan),'solver_ledger_sha256':ex.sha(ledger_raw),
               'solver_process':{'status':'ok','wall_seconds':0.2,'observed_peak_rss_bytes':1000,
                                 'path':f'{cell.name}/solver-process/process.json'},
               'e0_process':{'status':'ok','wall_seconds':0.1,'observed_peak_rss_bytes':1000,
                             'path':f'{cell.name}/e0-process/process.json'},
               'official':{'makespan':result['makespan'],'cross_task_traffic':result['cross_task_traffic'],
                           'movement':result['data_movement_bytes'],'result_sha256':ex.sha(result_raw)},
               'calls':{'E2_api_attempted':0,'native_returns':0,'E0_fallback_confirmed':0,
                        'E0_fallback_possible':0,'E0_independent_started':1},
               'request_in_flight':False}
        (cell/'cell.json').write_bytes(ex.jbytes({**row,'solver_process_in_flight':False,
                                                  'independent_e0_in_flight':False}))
        rows.append(row)
    summary = {'status':'running','accepted_cells':5,'rows':list(reversed(rows)), 'in_flight':[],
               'solver_commit':ex.SOLVER,'runner_commit':ex.RUNNER,
               'manifest_sha256':ex.sha(manifest_path.read_bytes()),'limits':manifest['limits'],
               'source':{'baseline_manifest_sha256':manifest['baseline_manifest']['sha256'],
                         'e2':{'commit':ex.E2},
                         'official_manifest_sha256':old['source_manifest_sha256']}}
    path=root/'summary.json'; path.write_bytes(ex.jbytes(summary))
    return path, manifest_path, summary


def test_compact_contract_and_board_schema():
    with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory(dir=ex.ROOT/'results/a/q2-nikolastarx') as out_dir:
        source, out = Path(source_dir), Path(out_dir)
        path, manifest, summary = fixture(source)
        old = ex.read(ex.ROOT/'results/a/q2-nikolastarx/gap-full500-20260925/manifest.json')
        assert len(ex.accepted_by_coordinate(summary, old)) == 5  # completion order is reversed
        receipt = ex.export(path,manifest,out,'synthetic-hypergap',1,1,'fixture/session',
                            'https://github.com/huaweibei123/huaweicup2026/issues/33','fixture','fixture/summary')
        assert receipt['records'] == 5 and receipt['evaluations'] == 0
        checked = subprocess.run([sys.executable,'-B','src/benchmark_board/protocol.py',receipt['feed'],'--submission'],
                                 cwd=ex.ROOT,capture_output=True,text=True)
        assert checked.returncode == 0 and json.loads(checked.stdout)['eligible'] == 5
        duplicate = copy.deepcopy(summary); duplicate['rows'].append(copy.deepcopy(duplicate['rows'][0]))
        try: ex.accepted_by_coordinate(duplicate,old)
        except ValueError: pass
        else: raise AssertionError('duplicate accepted')
        missing = copy.deepcopy(summary); missing['rows'].pop(); missing['accepted_cells']=4
        path.write_bytes(ex.jbytes(missing))
        try: ex.export(path,manifest,out,'synthetic-hypergap',1,1,'fixture/session','https://github.com/huaweibei123/huaweicup2026/issues/33','fixture','fixture/summary')
        except ValueError: pass
        else: raise AssertionError('missing core accepted')
        path.write_bytes(ex.jbytes(summary))
        row = summary['rows'][0]; cell = source/f"{row['case']}-k{row['cores']}"
        ledger = cell/'online/solver.json'; original = ledger.read_bytes(); ledger.write_bytes(original+b' ')
        try: ex.export(path,manifest,out,'synthetic-hypergap',1,1,'fixture/session','https://github.com/huaweibei123/huaweicup2026/issues/33','fixture','fixture/summary')
        except ValueError: pass
        else: raise AssertionError('ledger hash drift accepted')
        ledger.write_bytes(original)
        result = cell/'result.json'; raw = result.read_bytes(); bad = json.loads(raw); bad['makespan'] += 1; result.write_bytes(ex.jbytes(bad))
        try: ex.export(path,manifest,out,'synthetic-hypergap',1,1,'fixture/session','https://github.com/huaweibei123/huaweicup2026/issues/33','fixture','fixture/summary')
        except ValueError: pass
        else: raise AssertionError('official metric drift accepted')
