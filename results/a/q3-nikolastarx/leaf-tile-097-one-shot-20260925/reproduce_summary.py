"""Compare three existing lossless E0 timelines; no evaluation or reconstruction."""
import argparse
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT))
from src.q3.feedback_benchmark import digest, read
from src.q3.gap_frequency_probe import evidence


def metrics(result):
    ms = sorted((o for c in result['per_core_timeline'] for o in c['ops']
                 if o['pipe'] == 'PIPE_M'), key=lambda o: o['start'])
    gaps = [b['start'] - a['end'] for a, b in zip(ms, ms[1:])]
    assert min(gaps) >= 0
    busy = sum(o['duration'] for o in ms)
    first, tail = ms[0]['start'], result['makespan'] - ms[-1]['end']
    assert result['makespan'] == first + busy + sum(gaps) + tail
    return {'makespan_cycles': result['makespan'], 'm_count': len(ms), 'm_busy': busy,
            'first_m': first, 'tail': tail, 'total_m_gap': sum(gaps),
            'positive_m_gaps': sum(g > 0 for g in gaps), 'max_m_gap': max(gaps),
            'movement': result['data_movement_bytes'], 'cache_stats': result['cache_stats']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--forest-root', type=Path, required=True)
    a = parser.parse_args()
    manifest, run = read(OUT / 'manifest.json'), read(OUT / 'run.json')
    assert digest(OUT / 'manifest.json') == run['manifest_sha256']
    assert digest(OUT / 'plan.json') == run['plan_sha256']
    for path, sha in manifest['source_input_sha256'].items():
        assert digest(ROOT / path) == sha, path
    _, controls = evidence(a.forest_root, manifest['source_input_sha256'], manifest['official_code_sha256'])
    new = OUT / 'evaluation/result.json.gz'
    assert run['status'] == 'complete' and digest(new) == run['result_sha256']
    rows = [{'name': c['name'], 'plan_sha256': c['plan_sha256'],
             'result_sha256': c['result_sha256'], **metrics(read(c['result']))} for c in controls]
    rows.append({'name': 'leaf_tile_4x4', 'plan_sha256': run['plan_sha256'],
                 'result_sha256': run['result_sha256'], **metrics(read(new))})
    assert len({(r['m_count'], r['m_busy'], r['first_m'], r['tail']) for r in rows}) == 1
    old, new = rows[0], rows[-1]
    out = {'scope': 'one new 097/k1 P3 mechanism experiment; no new full500 solver score',
           'source_commit': manifest['source_commit'], 'new_p3_e0': 1, 'new_p2_e0': 0,
           'new_solver': 0, 'additional_task_step3_rebuilds': 0, 'rows': rows,
           'delta_vs_forest': {'makespan_cycles': new['makespan_cycles'] - old['makespan_cycles'],
                               'relative_m_reduction': 1 - new['makespan_cycles'] / old['makespan_cycles'],
                               'spill_bytes': new['movement']['spill_added_copy_bytes'] - old['movement']['spill_added_copy_bytes'],
                               'total_m_gap': new['total_m_gap'] - old['total_m_gap']},
           'limits': ['No P2 control for the new plan, so no new CacheGain claim.',
                      'Zero byte hits is not evidence of worse absolute Makespan.',
                      'Timeline gaps do not identify full critical predecessors; no new Task rebuild.',
                      'Runtime is construction plus external single E0, not a complete online solver.']}
    (OUT / 'summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(out['delta_vs_forest']))


if __name__ == '__main__':
    main()
