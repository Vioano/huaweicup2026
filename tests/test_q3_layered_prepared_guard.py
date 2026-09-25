"""Small synthetic captures; no official Task/Step/evaluator calls."""
from copy import deepcopy

from src.q3.layered_prepared_guard import PreparedGuardError, check_layered_prepared


def op(u, kind, pipe):
    return {'id': u, 'op': kind, 'pipe': pipe, 'cycles': 1}


def tensor(tid, pos='UB', size=1):
    return {'id': tid, 'pos': pos, 'size': size}


def edge(a, b, **extra):
    return {'source': a, 'target': b, **extra}


def task(core, ops, tensors, edges, seq, sg):
    g = {'ops': ops, 'tensors': tensors, 'edges': edges, 'seq_ext': seq}
    pipes = {p: [u for u in seq if next(o for o in ops if o['id'] == u)['pipe'] == p]
             for p in ('PIPE_MTE2', 'PIPE_MTE3', 'PIPE_M', 'PIPE_V')}
    return {'graph': g, 'seq': seq, 'op_by_id': {o['id']: o for o in ops},
            'tensor_by_id': {t['id']: t for t in tensors}, 'pipe_ops': pipes,
            'op_subgraph': {u: sg for u in seq},
            'step3': {'memory_peak': {'L1': 0, 'UB': 2},
                      'memory_dependencies': [], 'pipe_orders': deepcopy(pipes)}}


def fixture():
    graph = {'ops': [op(1, 'MATMUL', 'PIPE_M'), op(2, 'ADD', 'PIPE_V')],
             'tensors': [tensor(10), tensor(11), tensor(12)],
             'edges': [edge(10, 1), edge(1, 11), edge(11, 2), edge(2, 12)]}
    plan = {'node_to_subgraph': {'1': 0, '2': 1}, 'core_schedules': [[0], [1]]}
    first = task(0,
                 [op(100, 'COPY_IN', 'PIPE_MTE2'), op(1, 'MATMUL', 'PIPE_M'),
                  op(101, 'COPY_OUT', 'PIPE_MTE3')],
                 [tensor(10), tensor(11), tensor(1000, 'DDR'), tensor(1001, 'DDR')],
                 [edge(1000, 100), edge(100, 10), edge(10, 1), edge(1, 11),
                  edge(11, 101), edge(101, 1001)], [100, 1, 101], 0)
    second = task(1,
                  [op(102, 'COPY_IN', 'PIPE_MTE2'), op(2, 'ADD', 'PIPE_V'),
                   op(103, 'COPY_OUT', 'PIPE_MTE3')],
                  [tensor(11), tensor(12), tensor(1001, 'DDR'), tensor(1002, 'DDR')],
                  [edge(1001, 102), edge(102, 11), edge(11, 2), edge(2, 12),
                   edge(12, 103), edge(103, 1002)], [102, 2, 103], 1)
    steps = [{'seq_ext': seq, 'spill_records': [], 'overflow_log': [],
              'new_ops': [], 'new_tensors': [], 'new_edges': []}
             for seq in ([100, 1, 101], [102, 2, 103])]
    links = [{'tensor_id': 11, 'size': 1, 'source_core': 0, 'target_core': 1,
              'source_copy_out_id': 101, 'target_copy_in_id': 102}]
    captured = {'task_return': [{0: first, 1: second}, links, 1,
                                {'spill_added_copy_bytes': 0,
                                 'original_graph_copy_bytes': 0,
                                 'scheduled_copy_bytes': 4,
                                 'added_copy_bytes': 4}, {}],
                'step2': steps, 'capacity': {'L1': 2, 'UB': 2}}
    return graph, plan, captured


def rejection(graph, plan, capture, code):
    try:
        check_layered_prepared(graph, plan, capture, layers=1)
    except PreparedGuardError as error:
        assert error.code == code
        assert error.as_dict()['status'] == 'failed'
    else:
        raise AssertionError(f'expected {code}')


def test_complete_two_core_toy():
    report = check_layered_prepared(*fixture(), layers=1)
    assert report['status'] == 'passed'
    assert report['cross_links'] == report['max_crossing'] == 1
    assert report['edge_counts']['data_raw'] == 4


def test_backward_memory_dependency_is_rejected():
    graph, plan, captured = fixture()
    t = captured['task_return'][0][0]
    t['step3']['memory_dependencies'].append({'source': 101, 'target': 1})
    t['graph']['edges'].append(edge(101, 1, dependency='MEMORY_REUSE'))
    rejection(graph, plan, captured, 'memory_backward_bucket')


def test_missing_remote_copy_link_is_rejected():
    graph, plan, captured = fixture()
    captured['task_return'][1].clear()
    rejection(graph, plan, captured, 'cross_link_coverage')


def test_closed_frontier_overflow_is_rejected():
    graph, plan, captured = fixture()
    captured['capacity']['UB'] = 1
    rejection(graph, plan, captured, 'frontier_capacity')


def test_zero_byte_output_still_has_a_bucket():
    graph, plan, captured = fixture()
    graph['tensors'][2]['size'] = 0
    captured['task_return'][0][1]['graph']['tensors'][1]['size'] = 0
    captured['task_return'][0][1]['graph']['tensors'][3]['size'] = 0
    captured['task_return'][0][1]['tensor_by_id'][12]['size'] = 0
    captured['task_return'][0][1]['tensor_by_id'][1002]['size'] = 0
    captured['task_return'][3]['scheduled_copy_bytes'] = 3
    captured['task_return'][3]['added_copy_bytes'] = 3
    report = check_layered_prepared(graph, plan, captured, layers=1)
    assert report['status'] == 'passed'


if __name__ == '__main__':
    for name, value in sorted(globals().items()):
        if name.startswith('test_') and callable(value):
            value()
            print(f'PASS {name}')
