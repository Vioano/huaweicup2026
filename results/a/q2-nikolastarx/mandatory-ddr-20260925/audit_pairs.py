"""Static COPY audit of six immutable plans against their existing E0 artifacts."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.e2_plan_pairs import pinned


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / 'results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json'
    doc = json.loads(manifest_path.read_text())
    rows = []
    for pair in doc['pairs']:
        path = ROOT / pair['graph']['path']
        assert digest(path) == pair['graph']['sha256']
        graph = json.loads(path.read_text())
        for item in pair['plans']:
            plan, truth = pinned(item['plan']), pinned(item['truth'])
            count = mandatory_copy_work(graph, plan, truth['bandwidth_bytes_per_cycle'])
            movement = truth['data_movement_bytes']
            assert movement == item['expected_movement']
            assert count['transfer_bytes'] == (movement['scheduled_copy_bytes']
                                                - movement['spill_added_copy_bytes'])
            assert count['categories']['cross_tensor']['transfer_bytes'] + count['categories']['cross_direct']['transfer_bytes'] == 2 * truth['cross_task_traffic']
            assert count['service_work'] <= truth['makespan']
            rows.append({'pair': pair['name'], 'label': item['label'],
                         'plan': item['plan'], 'truth': item['truth'],
                         'counts': count, 'existing_E0_makespan': truth['makespan'],
                         'whole_E0_makespan': pair['plans'][0]['expected_makespan'],
                         'work_exceeds_whole_makespan': count['service_work'] > pair['plans'][0]['expected_makespan'],
                         'task_copy_bytes_match': True,
                         'cross_task_bytes_match': True})
    source_paths = ['src/q2_nikolastarx/candidate_ddr.py',
                    'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py',
                    'data/raw/a/official/code/multicore_cut_evaluate_problem_1.py',
                    'data/raw/a/official/code/schedule_step3.py']
    result = {'scope': 'Six existing plans, static counter only. No scheduling, simulation or solver calls.',
              'calls': {'solver': 0, 'E0': 0, 'E1': 0, 'E2': 0},
              'sources': {name: digest(ROOT/name) for name in source_paths},
              'manifest_sha256': digest(manifest_path),
              'audit_script_sha256': digest(Path(__file__)), 'rows': rows,
              'limitations': ['This is not a new algorithm performance batch.',
                              'Integer service-work model; no universal floating-point error proof.',
                              'Passing a lower bound does not establish a candidate improvement.']}
    out = Path(__file__).with_name('summary.json')
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps([{'pair': r['pair'], 'label': r['label'],
                       'bytes': r['counts']['transfer_bytes'],
                       'lower_work': r['counts']['service_work'],
                       'whole_M': r['whole_E0_makespan'],
                       'reject': r['work_exceeds_whole_makespan']} for r in rows], indent=2))


if __name__ == '__main__':
    main()
