"""Pure fixtures for the partial preload preparation guards; no official calls."""
import copy

import unittest

from src.q3.partial_preload_prepare import audit_prepared, serializable


def fixture():
    tasks, step1, step2, step3 = {}, [], [], []
    snapshots = {'candidate': {}}
    certificate = {'cores': []}
    words, prefixes = {}, {}
    for c in range(5):
        cold = [c * 100 + i for i in range(7 if c == 2 else 2)]
        compute = c * 100 + 20
        ids = cold + [compute]
        ops = [{'id': u, 'op': 'COPY_IN' if u in cold else 'COMPUTE',
                'pipe': 'PIPE_MTE2' if u in cold else 'PIPE_VECTOR'} for u in ids]
        graph = {'ops': ops, 'tensors': [], 'edges': []}
        task = {'seq': ids, 'op_by_id': {u: op for u, op in zip(ids, ops)},
                'op_preds': {u: [] for u in ids},
                'pipe_ops': {'PIPE_MTE2': cold[:], 'PIPE_VECTOR': [compute]},
                'step3': {'memory_dependencies': []}}
        tasks[c] = task
        step1.append({'graph': copy.deepcopy(graph), 'result': ids})
        step2.append({'seq': ids, 'result': {'spill_records': []}})
        step3.append({'result': {}})
        snapshots['candidate'][str(c)] = {'graph': graph}
        certificate['cores'].append({'core': c, 'prefix_copy_ids': cold})
        words[str(c)] = ids
        prefixes[str(c)] = cold[:6] if c == 2 else cold
    intermediates = {'Step1': step1, 'Step2': step2, 'Step3': step3}
    return tasks, [], intermediates, words, prefixes, snapshots, certificate, {'spill_added_copy_bytes': 0}


def test_valid_prepared_union():
    result = audit_prepared(*fixture())
    assert result['union_dag']['ops'] == 20


def test_reject_activation_before_six_cold_reads():
    data = list(fixture())
    data[1].append({'source_core': 0, 'source_copy_out_id': 20,
                    'target_core': 2, 'target_copy_in_id': 206})
    data[0][2]['pipe_ops']['PIPE_MTE2'].insert(0, 206)
    with unittest.TestCase().assertRaisesRegex(ValueError, 'cold prefix changed'):
        audit_prepared(*data)


def test_reject_step3_memory_cycle():
    data = list(fixture())
    data[0][2]['step3']['memory_dependencies'].append({'source': 220, 'target': 206})
    data[0][2]['op_preds'][220].append(206)
    with unittest.TestCase().assertRaisesRegex(ValueError, 'cycle'):
        audit_prepared(*data)


def test_reject_task_identity_change():
    data = list(fixture())
    data[2]['Step1'][0]['graph']['ops'][0]['id'] = -1
    with unittest.TestCase().assertRaisesRegex(ValueError, 'Task/COPY graph differs'):
        audit_prepared(*data)


def test_reject_pre_step2_word_mismatch():
    data = list(fixture())
    data[3]['0'] = list(reversed(data[3]['0']))
    with unittest.TestCase().assertRaisesRegex(ValueError, 'predicted pre-Step2'):
        audit_prepared(*data)


def test_serializable_preserves_numeric_keys_and_sets():
    assert serializable({2: {3, 1}}) == {'2': [1, 3]}
