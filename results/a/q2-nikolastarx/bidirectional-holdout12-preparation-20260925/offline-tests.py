"""No-score selection, three saved-cell replay, and fake supervisor checks."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

ROOT = next((p for p in Path(__file__).resolve().parents
             if (p/'scripts/q2_bidirectional_holdout.py').is_file()
             and (p/'pyproject.toml').is_file()), None)
if ROOT is None:
    raise RuntimeError('Cannot find project root with holdout runner and pyproject.toml')
OUT = ROOT/'output/bidirectional-holdout12-preparation-20260925'
required = [OUT/'selection-manifest.json',
            ROOT/'output/bidirectional-full500-preparation-20260925/local-full500-manifest.json',
            ROOT/'output/bidirectional-qualification-20260925/run-local-1/005-k5/solver/solver.json']
missing = [str(p) for p in required if not p.is_file()]
if missing:
    raise FileNotFoundError('Offline replay depends on original output fixtures: '+', '.join(missing))
REPO = Path('/Users/nikolastar/.codex/worktrees/p2-bidirectional-full500-s7d28/huaweicup2026')
RAW = Path('/Users/nikolastar/.codex/worktrees/q2-feedback-s8ee/huaweicup2026/data/raw/a/official')
E2 = Path('/Users/nikolastar/.codex/worktrees/q2-feedback-s8ee/huaweicup2026/output/q2-e2-paircheck-603b-s8ee')
PYTHON = Path('/Users/nikolastar/.codex/worktrees/p2-gap500-s59ee-20260925/huaweicup2026/.venv/bin/python')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load(ROOT/'scripts/q2_bidirectional_holdout.py', 'holdout')
sup = load(ROOT/'scripts/q2_bidirectional_holdout_supervise.py', 'holdout_supervisor')
assert sup.parse_pressure('1\n') == 1
assert sup.parse_swap_used('total = 2048.00M  used = 1287.12M  free = 760.88M  (encrypted)') > 0
for parser, malformed in ((sup.parse_pressure,'pressure = unknown'),
                          (sup.parse_swap_used,'used = unknown')):
    try:
        parser(malformed)
    except ValueError:
        pass
    else:
        raise AssertionError('Malformed sysctl accepted')
fixed = load(ROOT/'scripts/q2_bidirectional_local_full500.py', 'full500_preflight_only')
selection = json.loads((OUT/'selection-manifest.json').read_text())
ref = {'path': 'selection-manifest.json', 'sha256': m.SELECTION_SHA}
coords = m.load_selection({'selection_manifest': ref, 'coordinates': selection['coordinates']},
                          OUT/'placeholder-run-manifest.json', RAW)
assert len(coords) == 12 and all(k == 5 for _,k in coords)
assert coords == tuple(tuple(x) for x in selection['coordinates'])
for bad in ({'selection_manifest': {'path':'selection-manifest.json','sha256':'0'*64}, 'coordinates':selection['coordinates']},
            {'selection_manifest':ref, 'coordinates': list(reversed(selection['coordinates']))}):
    try:
        m.load_selection(bad, OUT/'placeholder-run-manifest.json', RAW)
    except ValueError:
        pass
    else:
        raise AssertionError('selection hash/order corruption accepted')

# Reuse the fixed full500 preflight solely to obtain checked source/E2 identities.
doc, identity, e2, _, _, _ = fixed.preflight(
    REPO, RAW, E2, PYTHON,
    ROOT/'output/bidirectional-full500-preparation-20260925/local-full500-manifest.json')
m.ROOT, m.RAW_ROOT, m.E2_ROOT, m.PYTHON, m.COORDS = REPO, RAW, E2, PYTHON, coords
assert PYTHON.is_symlink() and sup.invocation_python(PYTHON) == PYTHON
assert sup.invocation_python(PYTHON).resolve() != PYTHON
child_executable = subprocess.check_output([str(PYTHON), '-B', '-c',
                                            'import sys;print(sys.executable)'], text=True).strip()
assert child_executable == str(PYTHON)
m.runtime_import_preflight(PYTHON, E2)
try:
    m.runtime_import_preflight(PYTHON.resolve(), E2)
except ValueError as error:
    assert 'ModuleNotFoundError' in str(error) or 'venv not active' in str(error)
else:
    raise AssertionError('base interpreter unexpectedly passed venv import preflight')
qualification = ROOT/'output/bidirectional-qualification-20260925/run-local-1'
replayed = []
with tempfile.TemporaryDirectory(prefix='p2-holdout-offline-') as temporary:
    temp = Path(temporary)
    for case, cores in [('005',5),('069',5),('071',2)]:
        saved = qualification/f'{case}-k{cores}'
        dispatches = []
        def fake_monitor(argv, folder, deadline, rss):
            assert deadline > time.perf_counter() and rss == 2 << 30
            folder.mkdir(parents=True)
            cell = folder.parent
            if '-m' in argv:
                assert argv[argv.index('-m')+1] == m.MODULE
                shutil.copytree(saved/'solver', cell/'online')
                shutil.copyfile(saved/'plan.json',cell/'plan.json')
                receipt = saved/'solver-process/process.json'
                dispatches.append('saved-solver')
            else:
                assert argv[2] == str(REPO/'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py')
                shutil.copyfile(saved/'result.json',cell/'result.json')
                shutil.copyfile(saved/'trace.json',cell/'trace.json')
                receipt = saved/'E0-process/process.json'
                dispatches.append('saved-e0')
            shutil.copyfile(receipt,folder/'process.json')
            return json.loads(receipt.read_bytes())
        row = m.cell(case,cores,doc,identity,e2,fake_monitor,temp,time.perf_counter()+10)
        assert row['status'] == 'accepted', row
        assert dispatches == ['saved-solver','saved-e0']
        replayed.append(f'{case}-k{cores}')

    # One worker: the first failed cell must stop dispatch and reserve unknown fallback.
    m.COORDS = (('006',5),('019',5))
    calls = []
    original_cell = m.cell
    def failed_cell(case,cores,*unused):
        calls.append((case,cores))
        return {'case':case,'cores':cores,'status':'stopped','error':'missing ledger',
                'calls':{'E2_api_attempted':None,'native_returns':None,
                         'E0_fallback_possible':None,'E0_independent_started':0},
                'call_count_complete':False}
    m.cell = failed_cell
    d = {'runner_sha256':'offline','limits':m.LIMITS,
         'baseline_provenance':{},'singlecore_baseline':{'sha256':'offline'}}
    summary = m.run(d,identity,e2,None,'offline','offline',temp/'batch')
    m.cell = original_cell
    assert calls == [('006',5)] and summary['status'] == 'stopped_first_failure'
    assert summary['calls']['E0_fallback_possible'] == 1 and summary['call_count_complete'] is False

    pins = {'source_commit':sup.SOURCE, 'selection_sha256':sup.SELECTION_SHA,
            'runner_sha256': 'r'*64, 'manifest_sha256':'m'*64,'supervisor_sha256':'s'*64}
    gate = temp/'gate.json'
    expiry = lambda delta:(datetime.now(timezone.utc)+timedelta(seconds=delta)).isoformat()
    valid = {'status':'admitted','scope':sup.SCOPE,'expires_at_utc':expiry(30),**pins}
    gate.write_text(json.dumps(valid))
    sup.gate_check(gate,pins)
    for altered in ({**valid,'scope':'wrong'},
                    {**valid,'manifest_sha256':'bad'},
                    {**valid,'expires_at_utc':expiry(-1)}):
        gate.write_text(json.dumps(altered))
        try:
            sup.gate_check(gate,pins)
        except ValueError:
            pass
        else:
            raise AssertionError('bad or expired gate accepted')
    gate.write_text(json.dumps(valid))
    spec = importlib.util.spec_from_file_location('fixed_monitor',REPO/'src/q2_nikolastarx/evaluate_feedback.py')
    monitor = importlib.util.module_from_spec(spec); spec.loader.exec_module(monitor)
    paths = {'repo':REPO,'python':PYTHON,'runner':ROOT/'scripts/q2_bidirectional_holdout.py',
             'raw_root':RAW,'e2_root':E2,'manifest':OUT/'placeholder-run-manifest.json','gate':gate}
    actual_preflight = sup.preflight_paths
    sup.preflight_paths = lambda args:(paths,Path(args.output),pins,sup.gate_check(gate,pins),monitor)
    real_subprocess = sup.subprocess
    count = []
    def fake_popen(argv,**kwargs):
        count.append(1)
        return subprocess.Popen([str(PYTHON),'-B','-c','import time;time.sleep(20)'],**kwargs)
    sup.subprocess = SimpleNamespace(Popen=fake_popen)
    real_host_memory = sup.host_memory_state
    sup.host_memory_state = lambda: (1, 1000)
    original_deadline, original_sample = sup.DEADLINE_SECONDS,sup.SAMPLE_SECONDS
    sup.DEADLINE_SECONDS,sup.SAMPLE_SECONDS = 0.3,0.05
    try:
        args = SimpleNamespace(output=temp/'outer-timeout')
        try:
            sup.run(args)
        except SystemExit as exc:
            assert exc.code == 1
        receipt = json.loads((args.output/'supervisor-receipt.json').read_text())
        assert receipt['status'] == 'timeout' and receipt['surviving_pids'] == []
        assert len(count) == 1
        for label, sequence, expected in (
            ('pressure',[(1,1000),(2,1000)],'vm_pressure_limit'),
            ('swap',[(1,1000),(1,1000+sup.SWAP_DELTA_LIMIT+1)],'swap_growth_limit')):
            samples = iter(sequence)
            sup.host_memory_state = lambda: next(samples)
            args = SimpleNamespace(output=temp/('outer-'+label))
            try:
                sup.run(args)
            except SystemExit as exc:
                assert exc.code == 1
            receipt = json.loads((args.output/'supervisor-receipt.json').read_text())
            assert receipt['status'] == expected and receipt['surviving_pids'] == []
            assert receipt['vm_pressure_samples'] == 2 and receipt['swap_baseline_bytes'] == 1000
        assert len(count) == 3
        for label, altered in (('bad-scope',{**valid,'scope':'wrong'}),
                               ('bad-hash',{**valid,'manifest_sha256':'bad'}),
                               ('expired',{**valid,'expires_at_utc':expiry(-1)})):
            gate.write_text(json.dumps(altered))
            try:
                sup.run(SimpleNamespace(output=temp/('outer-'+label)))
            except ValueError:
                pass
            else:
                raise AssertionError(label+' unexpectedly dispatched')
            assert len(count) == 3
    finally:
        sup.preflight_paths = actual_preflight
        sup.subprocess = real_subprocess
        sup.host_memory_state = real_host_memory
        sup.DEADLINE_SECONDS,sup.SAMPLE_SECONDS = original_deadline,original_sample

result = {'selection_recomputed':list(coords),
          'venv_symlink_import_preflight':'passed',
          'saved_cell_replays':replayed,'unknown_fallback_reserved':1,
          'first_failure_dispatches':1,'gate_bad_scope_hash_expiry':'rejected',
          'fake_process_launches':3,'outer_timeout_cleanup':'passed',
          'vm_pressure_stop_cleanup':'passed','swap_growth_stop_cleanup':'passed',
          'new_solver_or_evaluator_calls':0,
          'holdout_runner_sha256':m.sha(ROOT/'scripts/q2_bidirectional_holdout.py'),
          'holdout_supervisor_sha256':sup.sha(ROOT/'scripts/q2_bidirectional_holdout_supervise.py'),
          'selection_sha256':m.SELECTION_SHA,
          'test_sha256':m.sha(Path(__file__))}
runtime_fix = ROOT/'output/holdout-runtime-fix-20260925'
runtime_fix.mkdir(parents=True, exist_ok=True)
(runtime_fix/'offline-test-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
