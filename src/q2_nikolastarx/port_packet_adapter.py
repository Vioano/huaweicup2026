"""Guarded official-graph adapter for the archived C04 construction prototype.

This constructs one singleton P2 priority plan. It does not call E0/E1/E2,
predict official Makespan, or establish Step3 execution feasibility. An
unsupported structure or failed static guard raises ``UnsupportedPortPacket``.
"""
from __future__ import annotations

from collections import defaultdict
import importlib.util
from pathlib import Path
import sys

from .direct import derive_multicore_plan, validate_graph
from .hypergraph_cost import HypergraphCost, UnsupportedHypergraph
from .packets import GraphIndex
from .zero_spill_intervals import certify


class UnsupportedPortPacket(ValueError):
    """C04 adapter abstains; this does not establish P2 infeasibility."""


_SOURCE = (Path(__file__).resolve().parents[2] / 'AI chats' /
           '20260925-P2-零spill通信与流水联合构造' /
           '附件' / 'c04-port_packet_stationary.browser-copy.py')


def _prototype():
    """Load the immutable browser-copy kernel without adding it to sys.path."""
    name = '_q2_c04_browser_copy'
    if name in sys.modules:
        return sys.modules[name]
    if not _SOURCE.is_file():
        raise UnsupportedPortPacket('C04 source artifact is unavailable')
    spec = importlib.util.spec_from_file_location(name, _SOURCE)
    if spec is None or spec.loader is None:
        raise UnsupportedPortPacket('C04 source artifact cannot be loaded')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclass annotations require registered module
    try:
        spec.loader.exec_module(module)
    except Exception:
        del sys.modules[name]
        raise
    return module


def to_ir(graph: dict, *, kernel=None):
    """Translate only a physical, tensor-mediated M/V computation DAG.

    Original COPY_IN outputs become independent external inputs. Original
    COPY_OUT consumption marks terminal outputs. Every retained dependency
    must then agree exactly with the official COPY-contracted GraphIndex.
    """
    try:
        validate_graph(graph)
        index = GraphIndex(graph)
    except Exception as error:
        raise UnsupportedPortPacket('official graph/index validation failed') from error
    if not index.ops:
        raise UnsupportedPortPacket('no eligible computation operations')
    if any(op['pipe'] not in ('PIPE_M', 'PIPE_V') or
           type(op['cycles']) is not int or op['cycles'] < 1
           for op in index.ops.values()):
        raise UnsupportedPortPacket('eligible operations require positive M/V cycles')
    if any('logical_tid' in t for t in index.tensors.values()):
        raise UnsupportedPortPacket('logical tensor aliases are unsupported')
    if any(type(t['size']) is not int or t['size'] < 0
           for t in index.tensors.values()):
        raise UnsupportedPortPacket('invalid physical tensor size')

    original_ops = {op['id']: op for op in graph['ops']}
    producers, consumers = defaultdict(set), defaultdict(set)
    copy_inputs = defaultdict(list)
    for edge in graph['edges']:
        source, target = edge['source'], edge['target']
        if source in original_ops and target in index.tensors:
            producers[target].add(source)
        elif source in index.tensors and target in original_ops:
            consumers[source].add(target)
            if original_ops[target]['op'] == 'COPY_IN':
                copy_inputs[target].append(source)
        elif source in index.ops and target in index.ops:
            raise UnsupportedPortPacket('direct eligible operation edge is unsupported')
    if any(len(producers[tid]) > 1 for tid in index.tensors):
        raise UnsupportedPortPacket('multiple original producers of a physical tensor')

    eligible = set(index.ops)
    tensors = []
    modeled = {u: set() for u in eligible}
    module = kernel if kernel is not None else _prototype()
    for tid in sorted(index.tensors):
        data = index.tensors[tid]
        source = producers[tid] & eligible
        targets = consumers[tid] & eligible
        if not (source or targets):
            continue
        copy_sources = producers[tid] - eligible
        if source and copy_sources:
            raise UnsupportedPortPacket('eligible and COPY producers share a tensor')
        if copy_sources and any(original_ops[u]['op'] != 'COPY_IN' for u in copy_sources):
            raise UnsupportedPortPacket('eligible input has unsupported COPY producer')
        if copy_sources:
            copy_id = next(iter(copy_sources))
            incoming = copy_inputs[copy_id]
            if not incoming or any(index.tensors[t]['pos'] != 'DDR' or
                                   producers[t] for t in incoming):
                raise UnsupportedPortPacket('COPY_IN is not an independent DDR input')
        producer = next(iter(source)) if source else None
        if producer is not None:
            modeled[producer].update(targets)
        required_output = bool(producer is not None and
                               (not targets or any(original_ops[u]['op'] == 'COPY_OUT'
                                                   for u in consumers[tid] - eligible)))
        tensors.append(module.Tensor(tid, data['size'],
                                     'UB' if data['pos'] == 'DDR' else data['pos'],
                                     producer, frozenset(targets), required_output))
    if modeled != {u: set(index.succs[u]) for u in eligible}:
        raise UnsupportedPortPacket('retained tensor DAG differs from official COPY-contracted DAG')
    ir = module.IR({u: index.ops[u]['pipe'] for u in eligible},
                   {u: index.ops[u]['cycles'] for u in eligible}, tuple(tensors))
    try:
        module.views(ir)
    except (ValueError, AssertionError) as error:
        raise UnsupportedPortPacket('C04 IR structural validation failed') from error
    return ir


def build(graph: dict, cores: int, config: dict, *, width: int = 32, kernel=None):
    """Return ``(plan, static_detail)`` or abstain before any official scoring."""
    if type(cores) is not int or not 1 <= cores <= 5:
        raise UnsupportedPortPacket('cores must be an integer in [1, 5]')
    try:
        capacity = config['capacity']
        bandwidth = config['bandwidth']
        delay = config['cross_core_copy_delay_cycles']
        if (not isinstance(capacity, dict) or set(capacity) != {'L1', 'UB'} or
            any(type(capacity[p]) is not int or capacity[p] <= 0 for p in capacity) or
            type(bandwidth) is not int or bandwidth <= 0 or
            type(delay) is not int or delay < 0):
            raise ValueError('invalid numeric configuration')
    except (KeyError, TypeError, ValueError) as error:
        raise UnsupportedPortPacket('requires positive integer capacity/bandwidth and nonnegative delay') from error
    module = kernel if kernel is not None else _prototype()
    ir = to_ir(graph, kernel=module)
    try:
        rows, detail = module.build(ir, cores, capacity, width=width,
                                    bandwidth=bandwidth, delay=delay)
    except (module.NoCandidate, ValueError, AssertionError, KeyError, TypeError) as error:
        raise UnsupportedPortPacket('C04 constructor abstained: ' + str(error)) from error
    if len(rows) != cores or [u for row in rows for u in row] == []:
        raise UnsupportedPortPacket('C04 returned invalid core rows')
    mapping = {str(u): u for u in sorted(ir.pipe)}
    try:
        plan = module.emit_singletons(mapping, rows)
        if set(plan) != {'node_to_subgraph', 'core_schedules'} or plan['node_to_subgraph'] != mapping:
            raise ValueError('singleton mapping changed')
        derive_multicore_plan(graph, plan)
    except Exception as error:
        raise UnsupportedPortPacket('official singleton plan structural validation failed') from error
    certificate = certify(graph, plan, config)
    if not certificate['supported']:
        raise UnsupportedPortPacket('physical zero-spill guard unsupported: ' + certificate['reason'])
    if not certificate['zero_spill_certificate']:
        raise UnsupportedPortPacket('physical zero-spill guard exceeded capacity')
    try:
        owner = {u: core for core, row in enumerate(rows) for u in row}
        exact_bytes = HypergraphCost(graph, ir.pipe).state(owner).total_bytes
    except (UnsupportedHypergraph, ValueError) as error:
        raise UnsupportedPortPacket('physical COPY-byte guard unsupported') from error
    if exact_bytes != detail['pre_step2_copy_bytes']:
        raise UnsupportedPortPacket('C04 and physical COPY-byte ledgers disagree')
    detail = {**detail, 'pending': ['official E0 acceptance']}
    return plan, {'constructor': detail, 'zero_spill': certificate,
                  'physical_pre_step2_copy_bytes': exact_bytes,
                  'scope': 'static singleton priority; no E0/E1/E2 or Step3 acceptance'}
