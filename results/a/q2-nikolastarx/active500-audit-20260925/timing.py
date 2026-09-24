"""Summarize recorded solver and external E0 time; never run an evaluator."""
from pathlib import Path
import csv
import hashlib
import json
import math
import statistics


def main():
    source = Path(__file__).with_name('paired.csv')
    rows = list(csv.DictReader(source.open()))
    keys = {(r['case_id'], int(r['cores'])) for r in rows}
    assert len(rows) == len(keys) == 500
    assert keys == {(f'{case:03}', k) for case in range(1, 101) for k in range(1, 6)}
    groups = {}
    for name, selected in [('all', rows)] + [
        (str(k), [r for r in rows if int(r['cores']) == k]) for k in range(1, 6)
    ]:
        groups[name] = {}
        for field in ('new_solver_wall_s', 'new_E0_wall_s'):
            values = sorted(float(r[field]) for r in selected)
            assert all(math.isfinite(v) and v >= 0 for v in values)
            groups[name][field] = dict(
                n=len(values), mean=statistics.mean(values),
                median=statistics.median(values),
                p95_nearest_rank=values[math.ceil(.95 * len(values)) - 1],
                maximum=max(values), minimum=min(values),
            )
    result = {
        'input': source.name,
        'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'unit': 'seconds', 'groups': groups,
        'scope': 'Existing full500 batch with four concurrent workers; not exclusive-machine latency. Solver and external final E0 remain separate.',
        'new_solver_or_evaluator_calls': 0,
    }
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
