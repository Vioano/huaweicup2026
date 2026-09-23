"""Pack actual, globally validated Scene B tasks; retain original FIFO/sort order."""
import ctypes as ct
from dataclasses import dataclass
from pathlib import Path
import sys
import numpy as np
from ._native import I32P, I64P, U8P, PIPES, Unsupported, array, ptr

I32_FIELDS = ('slot', 'next_pipe', 'heads', 'pred_count', 'succ_off', 'succ',
              'cross_count', 'cross_off', 'cross_succ', 'sort_rank')

class InputB(ct.Structure):
    _fields_ = [('n', ct.c_int32), ('c', ct.c_int32)] + [(x, I32P) for x in I32_FIELDS] + [
        ('duration', I64P), ('ddr', U8P), ('cross_wait', ct.c_int64), ('max_iter', ct.c_int64)]

class OutputB(ct.Structure):
    _fields_ = [(x, I64P) for x in ('op_start', 'op_end', 'stats')]

@dataclass
class CompiledB:
    arrays: dict
    cores: int
    op_keys: object
    total_duration: int


def pack(tasks, cross_links, runtime, bandwidth):
    c = len(tasks)
    if tuple(tasks) != tuple(range(c)) or not 1 <= c <= 128:
        raise Unsupported('native Scene B requires 1..128 contiguous cores')
    keys = tuple((t, o) for t in tasks for o in tasks[t]['seq'])
    ix = {k: i for i, k in enumerate(keys)}
    n = len(keys)
    if len(ix) != n or n >= 2**31:
        raise Unsupported('native index domain')
    a = {name: [] for name in I32_FIELDS}
    a.update(heads=[-1]*(4*c), next_pipe=[-1]*n, sort_rank=[0]*n,
             cross_count=[0]*n, succ_off=[0], cross_off=[0])
    duration, ddr = [], []
    for core, task in tasks.items():
        for pipe, order in task['pipe_ops'].items():
            if pipe not in PIPES:
                raise Unsupported('unknown pipe')
            if order:
                a['heads'][4*core+PIPES.index(pipe)] = ix[core, order[0]]
            for x, y in zip(order, order[1:]):
                a['next_pipe'][ix[core, x]] = ix[core, y]
        for oid in task['seq']:
            op = task['op_by_id'][oid]
            d = runtime._op_duration(op, task['in_tids'], task['out_tids'], task['tensor_by_id'], bandwidth)
            if type(d) is not int or not 1 <= d < 2**50:
                raise Unsupported('native duration domain')
            duration.append(d)
            ddr.append(runtime._uses_ddr_bandwidth(op, task['in_tids'], task['out_tids'], task['tensor_by_id']))
            a['slot'].append(4*core+PIPES.index(runtime.op_pipe(op)))
            a['pred_count'].append(len(task['op_preds'][oid]))
            a['succ'].extend(ix[core, s] for s in task['op_succs'][oid])
            a['succ_off'].append(len(a['succ']))
    cross = [[] for _ in keys]
    for link in cross_links:
        source = ix[link['source_core'], link['source_copy_out_id']]
        target = ix[link['target_core'], link['target_copy_in_id']]
        cross[source].append(target)
        a['cross_count'][target] += 1
    for row in cross:
        a['cross_succ'].extend(row)
        a['cross_off'].append(len(a['cross_succ']))
    for rank, key in enumerate(sorted(keys)):
        a['sort_rank'][ix[key]] = rank
    if max(len(a['succ']), len(a['cross_succ'])) >= 2**31:
        raise Unsupported('native edge domain')
    a = {name: array(value) for name, value in a.items()}
    a['duration'], a['ddr'] = array(duration, np.int64), array(ddr, np.uint8)
    return CompiledB(a, c, keys, sum(duration))


_LIB = None
def get_lib():
    global _LIB
    if _LIB is None:
        suffix = '.dll' if sys.platform == 'win32' else '.so'
        library = ct.CDLL(str(Path(__file__).parent / ('native/libreplay_b'+suffix)))
        library.replay_b.argtypes = [ct.POINTER(InputB), ct.POINTER(OutputB)]
        library.replay_b.restype = ct.c_int
        _LIB = library
    return _LIB


def score(comp, *, cross_core_copy_delay, max_iter):
    if type(cross_core_copy_delay) is not int or cross_core_copy_delay < 0 or type(max_iter) is not int or not 1 <= max_iter < 2**63:
        raise Unsupported('native integer delay/iteration domain')
    n = len(comp.op_keys)
    if comp.total_duration*(4*comp.cores+1)+(cross_core_copy_delay+1)*n+4*n >= 2**50:
        raise Unsupported('native conservative time bound exceeded')
    inp = InputB(n=n, c=comp.cores, cross_wait=cross_core_copy_delay, max_iter=max_iter)
    for name, value in comp.arrays.items():
        setattr(inp, name, ptr(value, I64P if name == 'duration' else U8P if name == 'ddr' else I32P))
    result = {name: np.empty(size, np.int64) for name, size in (('op_start', n), ('op_end', n), ('stats', 8))}
    out = OutputB(**{k: ptr(v, I64P) for k, v in result.items()})
    status = get_lib().replay_b(ct.byref(inp), ct.byref(out))
    if status:
        raise Unsupported(f'native Scene B status={status}; official fallback required')
    result['makespan'] = int(result['stats'][0])
    return result
