"""Compare fixed saved tables with a common per-case denominator; no scoring."""
from pathlib import Path
import csv
import hashlib
import io
import json
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[4]
FANG = '71616ac7c4c7fca56e37e2d3245dd13725316d82'
OURS = 'ee4fe0282ca2ff5d73bb23d54b1c213909e1401c'
BASE = 'results/a/q2-yuanzhifang/feedback-20260924/full-coverage/'


def read(commit, path):
    raw = subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)
    return list(csv.DictReader(io.StringIO(raw.decode()))), {
        'commit': commit, 'path': path, 'sha256': hashlib.sha256(raw).hexdigest()}


def main():
    ours, own_ref = read(OURS, 'results/a/q2-nikolastarx/active500-audit-20260925/paired.csv')
    index = {(r['case_id'], int(r['cores'])): r for r in ours}
    assert len(index) == len(ours) == 500
    report = {'own_source': own_ref, 'new_evaluator_calls': 0, 'comparisons': []}
    for family, ks in [('all500', range(1, 6)), ('gap-k2k3-200', range(2, 4))]:
        other, ref = read(FANG, BASE + family + '/per-cell.csv')
        coordinates = {(r['case_id'], int(r['cores'])) for r in other}
        assert len(other) == len(coordinates) == 100 * len(ks)
        assert coordinates == {(f'{case:03}', k) for case in range(1, 101) for k in ks}
        totals = []
        for k in ks:
            selected = [r for r in other if int(r['cores']) == k]
            own = [index[r['case_id'], k] for r in selected]
            assert all(int(a['baseline_cycles']) == int(b['baseline_B']) for a, b in zip(selected, own))
            delta = [int(b['new_M']) - int(a['makespan_cycles']) for a, b in zip(selected, own)]
            totals.append({
                'cores': k, 'n': len(selected),
                'fang_mean': statistics.mean(int(r['baseline_cycles']) / int(r['makespan_cycles']) for r in selected),
                'our_mean': statistics.mean(int(r['baseline_B']) / int(r['new_M']) for r in own),
                'our_wins_losses_ties': [sum(d < 0 for d in delta), sum(d > 0 for d in delta), sum(d == 0 for d in delta)],
                'fang_extra_ddr_bytes': sum(int(r['extra_ddr_bytes']) for r in selected),
                'our_extra_ddr_bytes': sum(int(r['new_extra_ddr_bytes']) for r in own),
            })
        report['comparisons'].append({'family': family, 'source': ref, 'rows': totals})
    report['scope'] = ('Fixed CSV arithmetic and equal baseline values only; not a new independent audit of all Fang plan/result identities. '
                       'No historical per-cell portfolio is constructed. Different hardware prevents direct solver-time comparisons.')
    path = Path(__file__).with_name('comparison.json')
    with path.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report['comparisons'], indent=2))


if __name__ == '__main__':
    main()
