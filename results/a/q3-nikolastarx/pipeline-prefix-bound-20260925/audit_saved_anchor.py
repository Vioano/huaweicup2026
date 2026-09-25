"""Compare the bound with an existing official result; no evaluator imports."""
from pathlib import Path
import gzip
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
RESULT = ROOT / 'results/a/q3-nikolastarx/pipeline-capacity-two-shot-20260925/evaluation/044/result.json.gz'
EXPECTED = '506a8d65c65b7bcd2957e2b20f31ba117fb3a244b9c366ff2342c421df626cd5'


def main():
    raw = RESULT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    result = json.loads(gzip.decompress(raw))
    bound = json.loads((OUT / 'anchor.json').read_text())
    ops = {(core['core_id'], op['op_id']): op
           for core in result['per_core_timeline'] for op in core['ops']}
    failures = []
    for op in bound['copy_nodes']:
        seen = ops[(op['core'], op['op_id'])]
        if seen['duration'] < op['duration_lower_bound']:
            failures.append(['duration', op['core'], op['op_id']])
        if op['kind'] == 'COPY_IN':
            if seen.get('cache_tensor_id') != op['cache_key']:
                failures.append(['cache_key', op['core'], op['op_id']])
            if op['sole_copy_in_key_proved_cold'] and seen.get('cache_hit') is not False:
                failures.append(['cold', op['core'], op['op_id']])
    for op in bound['critical_path']:
        seen = ops[(op['core'], op['op_id'])]
        if seen['start'] < op['earliest_start']:
            failures.append(['path_start', op['core'], op['op_id']])
    if result['makespan'] < bound['lower_bound_cycles']:
        failures.append(['makespan'])
    report = {'scope': 'existing official anchor trace only; candidate remains unscored',
              'official_result_sha256': EXPECTED,
              'anchor_bound_sha256': hashlib.sha256((OUT / 'anchor.json').read_bytes()).hexdigest(),
              'official_makespan': result['makespan'], 'lower_bound_cycles': bound['lower_bound_cycles'],
              'checked_copy_nodes': len(bound['copy_nodes']),
              'checked_path_nodes': len(bound['critical_path']),
              'cold_key_nodes': bound['sole_copy_in_key_count'],
              'failures': failures, 'new_evaluator_calls': 0}
    (OUT / 'anchor-trace-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    assert not failures, failures
    print(json.dumps(report))


if __name__ == '__main__':
    main()
