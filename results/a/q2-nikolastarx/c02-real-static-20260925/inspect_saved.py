"""One unscored C02 construction from archived 069/K5 evidence."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx import exit_sealed_candidate
from src.q2_nikolastarx.dag_direct import DAGIndex
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--raw', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--adapter-file', type=Path)
    args = p.parse_args()
    args.output.mkdir(exist_ok=False)
    archive = ROOT / 'results/a/q2-nikolastarx'
    saved_zip = archive / 'native-packet-069-pilot-20260925/results.zip'
    assert hashlib.sha256(saved_zip.read_bytes()).hexdigest() == 'd14737694cbdb69295b812921ce11d4b56788e6204bb390988c81c4876f2c1aa'
    with zipfile.ZipFile(saved_zip) as z:
        diag = json.loads(z.read('output/native-diagnostic.json'))
    base = archive / 'hypergap-full500-archive-20260924T233302Z-s8ee/cases-061-070/069-k5'
    plan = json.loads(gzip.decompress((base / 'plan.json.gz').read_bytes()))
    graph = json.loads((args.raw / 'case_069.json').read_bytes())
    cfg_file = args.raw / 'config.txt'
    config = {**read_evaluation_config(cfg_file), **read_scene_b_config(cfg_file)}
    native_config = {'capacity': config['capacity'], 'bandwidth': config['bandwidth'],
                     'cross_core_copy_delay': config['cross_core_copy_delay_cycles'], 'max_iter': 1000000}
    for key, value in [('graph', graph), ('plan', plan), ('config', native_config)]:
        assert fingerprint(value) == diag['input_identity'][key + '_canonical_sha256'], key
    eligible = set(DAGIndex(graph).ops)
    finish = {}
    for core in diag['trace_result']['per_core_timeline']:
        for op in core['ops']:
            if op['op_id'] in eligible:
                assert op['op_id'] not in finish
                finish[op['op_id']] = op['end']
    assert set(finish) == eligible
    adapter = exit_sealed_candidate
    if args.adapter_file:
        spec = importlib.util.spec_from_file_location('src.q2_nikolastarx.c02_static_override', args.adapter_file)
        adapter = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = adapter
        spec.loader.exec_module(adapter)
    start = time.perf_counter()
    candidates, meta = adapter.propose(graph, plan, config,
        diag['critical_links'], finish, incumbent_makespan=diag['score']['makespan'])
    elapsed = time.perf_counter() - start
    for i, candidate in enumerate(candidates):
        (args.output / f'candidate-{i:02}.json').write_text(json.dumps(candidate, indent=2) + '\n')
    report = {'source_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'case': '069', 'cores': 5, 'diagnostic_zip_sha256': hashlib.sha256(saved_zip.read_bytes()).hexdigest(),
        'identity_verified': diag['input_identity'], 'eligible_ops': len(eligible),
        'saved_critical_links': len(diag['critical_links']), 'construction_seconds': elapsed,
        'propose_calls': 1, 'E0': 0, 'E1': 0, 'E2': 0, 'meta': meta,
        'adapter_override': str(args.adapter_file) if args.adapter_file else None,
        'adapter_sha256': hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest(),
        'candidate_details': [c['detail'] for c in candidates],
        'limitation': 'Saved-trace-assisted structural construction only; no new score or online solver result.'}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))

if __name__ == '__main__':
    main()
