"""Bounded ordered-family MEM response probe; research candidate, never E0.

Every profiled Task is compiled at its actual core and position. Only identical
node tuples reuse a compile; Family.prekey is deliberately unused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import threading
import time

from src.q1.capacity_return import author
from src.q1.compiled_memory_response import compile_plan, _check_original
from src.q1.packet_dp import _TaskProjection
from src.q1.response_compile import UnsupportedResponse, _official_modules
from src.q1.response_oracle import quotient, simulate
from src.q1.variable_packet import Family


ROOT = Path(__file__).resolve().parents[2]


class MemoryFamily(Family):
    """Keep the strict ordered/private Family proof; remove footprint gating."""
    def __init__(self, graph, cores, capacity, bandwidth):
        self.graph, self.cores = graph, cores
        self.capacity, self.bandwidth = capacity, bandwidth
        self.view, self.chains, self.chain_tensors, _, _ = author.recognize(graph)
        v = self.view
        self.eligible = {u for chain in self.chains for u in chain}
        self.has_out = {tid: any(v.ops[u]['op'] == 'COPY_OUT'
                                 for u in v.consumers[tid]) for tid in v.tensors}
        self.direct = {u: [] for u in self.eligible}
        for edge in graph['edges']:
            if edge['source'] in self.eligible and edge['target'] in self.eligible:
                self.direct[edge['source']].append(edge)
        self.next_id = max(set(v.ops) | set(v.tensors), default=0) + 1
        _, _, _, validation = _official_modules()
        validation.validate_graph(graph)
        _check_original(graph, capacity)
        self.verify_ordered_family()
        self.projection = _TaskProjection(graph, v)
        self.bins = [self.chains[k::cores] for k in range(cores)]
        self.B = len(self.chains) // cores
        self.P = self.footprint(self.chains[0][:-1])
        self.R = self.footprint(self.chains[0][-1:])
        self.W = self.footprint(self.chains[0])


def solve_acyclic(B, rmax, qmax, transition, terminal):
    """Pure (n,r) DP: drain r>0 at fixed n, normal edge strictly grows n."""
    dist = [{} for _ in range(B + 1)]
    dist[0][0] = ((0, 0, 0), ())
    def add(a, b):
        return tuple(x + y for x, y in zip(a, b))
    for n in range(B + 1):
        for r, (cost, path) in list(dist[n].items()):
            if not r:
                continue
            value = transition(n, r, 0, 0, True)
            if value is None:
                continue
            candidate = add(cost, value)
            if 0 not in dist[n] or candidate < dist[n][0][0]:
                dist[n][0] = (candidate, path + ((n, r, 0, 0),))
        if n == B:
            break
        for r, (cost, path) in dist[n].items():
            for q in range(1, min(qmax, B - n) + 1):
                for s in range(min(q, rmax) + 1):
                    value = transition(n, r, q, s, False)
                    if value is None:
                        continue
                    candidate = add(cost, value)
                    if s not in dist[n + q] or candidate < dist[n + q][s][0]:
                        dist[n + q][s] = (candidate, path + ((n, r, q, s),))
    best = None
    for r, (cost, path) in dist[B].items():
        for policy in ('merge', 'separate'):
            ending = terminal(r, policy)
            if ending is None:
                continue
            key = (add(cost, ending), policy, r)
            if best is None or key < best[0]:
                best = (key, path)
    return None if best is None else dict(cost=best[0][0], policy=best[0][1],
                                           pending=best[0][2], actions=best[1])


class Kernel:
    def __init__(self, family, gate, limit, deadline):
        self.f, self.gate, self.limit, self.deadline = family, gate, limit, deadline
        self.tasks = {}
        self.responses = {}
        self.requests = self.hits = self.compiles = 0
        self.completed = 0
        self.full_plan_attempted_bound = self.full_plan_completed = 0
        self.rejected = []

    def check(self):
        if time.perf_counter() >= self.deadline:
            raise TimeoutError('60-second construct deadline')

    def get(self, nodes):
        self.check()
        key = tuple(nodes)
        if not key:
            raise ValueError('empty Task')
        self.requests += 1
        if key in self.tasks:
            self.hits += 1
            return self.tasks[key]
        if self.compiles >= self.limit:
            raise RuntimeError('2500 Task compilation limit')
        self.compiles += 1
        local = self.f.projection.graph(nodes)
        plan = {'node_to_subgraph': {str(u): 0 for u in nodes},
                'core_schedules': [[0]]}
        lines, cert = compile_plan(local, plan, self.f.capacity, self.f.bandwidth)
        self.completed += 1
        self.check()
        item = {'task': lines[0][0], 'bytes': cert['traffic']['scheduled_copy_bytes']}
        self.tasks[key] = item
        return item

    def profile(self, n, r, q, s, drain=False):
        self.check()
        groups = [self.f.members(k, n, r, q, s) for k in range(self.f.cores)]
        try:
            items = [self.get(nodes) for nodes in groups]
        except UnsupportedResponse as error:
            self.rejected.append({'state': [n, r, q, s], 'drain': drain,
                                  'reason': str(error)})
            return None
        signatures = tuple(item['task'].signature() for item in items)
        if any(signature != signatures[0] for signature in signatures[1:]):
            self.rejected.append({'state': [n, r, q, s], 'drain': drain,
                                  'reason': 'actual per-core signatures differ'})
            return None
        if signatures not in self.responses:
            self.responses[signatures] = simulate([[item['task']] for item in items], self.gate)
        return (self.responses[signatures]['makespan'] + self.gate,
                sum(item['bytes'] for item in items), self.f.cores)

    def suffix(self, r, policy, old_merge_guard=False):
        self.check()
        f = self.f
        all_groups, lines, traffic = [], [], 0
        for k in range(f.cores):
            old = f.members(k, f.B, r, 0, 0) if r else []
            remainder = [u for c in f.bins[k][f.B:] for u in c]
            if policy == 'merge':
                nodes = old + remainder
                if old_merge_guard and any(v > f.capacity[p]
                                           for p, v in f.footprint(nodes).items()):
                    return None
                groups = [nodes] if nodes else []
            else:
                groups = [x for x in (old, remainder) if x]
            try:
                items = [self.get(nodes) for nodes in groups]
            except UnsupportedResponse as error:
                self.rejected.append({'terminal': [r, policy, k], 'reason': str(error)})
                return None
            all_groups.append(groups)
            lines.append([item['task'] for item in items])
            traffic += sum(item['bytes'] for item in items)
        response = simulate(lines, self.gate) if any(lines) else {'makespan': 0}
        return {'groups': all_groups, 'cost': (response['makespan'] + self.gate,
                                               traffic, sum(map(len, lines)))
                if any(lines) else (0, 0, 0)}


def _construct(graph, cores, capacity, bandwidth, gate, limit, seconds, state):
    started = time.perf_counter()
    deadline = started + seconds
    state['stage'] = 'family_validation'
    family = MemoryFamily(graph, cores, capacity, bandwidth)
    kernel = Kernel(family, gate, limit, deadline)
    state['kernel'] = kernel
    state['stage'] = 'profile_and_dp'
    B = family.B
    old_q = min([B] + [capacity[p] // size for p, size in family.P.items() if size])
    old_r = min([old_q] + [capacity[p] // size for p, size in family.R.items() if size])
    old_q, old_r = min(old_q, 2), min(old_r, 2)
    terminal_cache = {}

    def terminal(r, policy, old=False):
        key = (r, policy, old)
        if key not in terminal_cache:
            terminal_cache[key] = kernel.suffix(r, policy, old_merge_guard=old)
        item = terminal_cache[key]
        return None if item is None else item['cost']

    def transition(n, r, q, s, drain, old=False):
        if old and (r > old_r or q > old_q or s > old_r or
                    (not drain and not family.fits(r, q, s))):
            return None
        return kernel.profile(n, r, q, s, drain)

    old = solve_acyclic(B, old_r, old_q,
                        lambda *args: transition(*args, old=True),
                        lambda r, p: terminal(r, p, old=True))
    new = solve_acyclic(B, 2, 2, transition,
                        lambda r, p: terminal(r, p))
    if new is None:
        raise UnsupportedResponse('no supported q/r<=2 path')
    chosen_terminal = terminal_cache[new['pending'], new['policy'], False]
    mapping, orders, expected = {}, [[] for _ in range(cores)], []
    task_count = 0
    for k in range(cores):
        groups = [family.members(k, *action) for action in new['actions']]
        groups += chosen_terminal['groups'][k]
        signatures = []
        for nodes in groups:
            if not nodes:
                raise AssertionError('empty selected Task')
            item = kernel.tasks[tuple(nodes)]
            signatures.append(item['task'].signature())
            orders[k].append(task_count)
            for u in nodes:
                if u in mapping:
                    raise AssertionError('duplicate compute member')
                mapping[u] = task_count
            task_count += 1
        expected.append(signatures)
    plan = {'node_to_subgraph': {str(op['id']): mapping[op['id']]
                                 for op in graph['ops'] if op['op'] not in author.COPY},
            'core_schedules': orders}
    author.validate_plan_structure(graph, plan)
    if kernel.compiles + task_count > limit:
        raise RuntimeError('2500 Task compilation limit before full plan')
    kernel.check()
    state['stage'] = 'final_full_plan_compile'
    kernel.full_plan_attempted_bound = task_count
    lines, certificate = compile_plan(graph, plan, capacity, bandwidth)
    kernel.compiles += task_count
    kernel.completed += task_count
    kernel.full_plan_completed = task_count
    kernel.check()
    state['stage'] = 'final_signature_and_cost_verification'
    for core, line in enumerate(lines):
        if len(line) != len(expected[core]) or any(
                task.signature() != signature
                for task, signature in zip(line, expected[core])):
            raise UnsupportedResponse('final full-plan Task signature changed')
    actual = quotient(lines, gate)
    predicted = new['cost'][0] - gate
    if actual['makespan'] != predicted:
        raise UnsupportedResponse('full-plan rational replay differs from DP')
    if certificate['traffic']['scheduled_copy_bytes'] != new['cost'][1]:
        raise UnsupportedResponse('full-plan DDR bytes differ from DP')
    return plan, {
        'kind': 'bounded-memory-packet-research-NOT-E0',
        'family': family.family_certificate, 'cores': cores, 'B': B,
        'q_limit': 2, 'r_limit': 2, 'old_q_limit': old_q, 'old_r_limit': old_r,
        'old_domain': old, 'new_domain': new,
        'model_makespan_delta_new_minus_old': (new['cost'][0] - old['cost'][0])
        if old else None,
        'plan_tasks': task_count, 'task_compile_requests': kernel.requests,
        'task_compile_hits': kernel.hits,
        'task_compiles_including_full_plan': kernel.compiles,
        'task_compile_attempted_budget': kernel.compiles,
        'task_compile_confirmed_completed': kernel.completed,
        'final_full_plan_confirmed_completed': kernel.full_plan_completed,
        'task_compile_limit': limit, 'construct_seconds': time.perf_counter() - started,
        'rejected': kernel.rejected, 'response': actual,
        'compilation_certificate': certificate,
        'calls': {'candidate_constructors': 1, 'E0': 0, 'E1': 0, 'E2': 0},
        'scope': 'strict ordered private Family; q/r<=2 mechanism experiment only; '
                 'not structural, P1, or E0 optimality',
    }


def construct(graph, cores, capacity, bandwidth=60, gate=100,
              max_task_compiles=2500, timeout_seconds=60):
    if type(cores) is not int or not 1 <= cores <= 5:
        raise ValueError('cores must be 1..5')
    if set(capacity) != {'L1', 'UB'} or any(type(v) is not int or v <= 0
                                            for v in capacity.values()):
        raise ValueError('positive L1/UB capacities required')
    if type(bandwidth) is not int or bandwidth < 1 or type(gate) is not int or gate < 0:
        raise ValueError('invalid bandwidth or gate')
    if type(max_task_compiles) is not int or not 1 <= max_task_compiles <= 2500:
        raise ValueError('max_task_compiles must be 1..2500')
    if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 60:
        raise ValueError('timeout_seconds must be in (0,60]')
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('hard timeout requires main thread')
    if signal.getitimer(signal.ITIMER_REAL)[0]:
        raise RuntimeError('refuse to replace an active process timer')
    previous = signal.getsignal(signal.SIGALRM)
    def expired(_signum, _frame):
        raise TimeoutError('60-second construct deadline')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
    state = {'stage': 'initialization', 'kernel': None}
    try:
        return _construct(graph, cores, capacity, bandwidth, gate,
                          max_task_compiles, timeout_seconds, state)
    except Exception as error:
        kernel = state['kernel']
        error.response_probe_diagnostics = {
            'status': 'failed', 'stage': state['stage'],
            'error_type': type(error).__name__, 'error': str(error),
            'calls': {'candidate_constructors': 1, 'E0': 0, 'E1': 0, 'E2': 0},
            'task_compile_attempted_budget': (
                kernel.compiles + kernel.full_plan_attempted_bound -
                kernel.full_plan_completed if kernel else 0),
            'task_compile_confirmed_completed': kernel.completed if kernel else 0,
            'final_full_plan_attempted_upper_bound': (
                kernel.full_plan_attempted_bound if kernel else 0),
            'final_full_plan_confirmed_completed': (
                kernel.full_plan_completed if kernel else 0),
            'rejected': kernel.rejected if kernel else [],
        }
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graph', type=Path)
    parser.add_argument('--cores', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostics', type=Path, required=True)
    args = parser.parse_args()
    if args.output == args.diagnostics or args.output.exists() or args.diagnostics.exists():
        raise FileExistsError('refuse to overwrite output')
    try:
        _official_modules()
        from evaluation_validation import read_evaluation_config
        from multicore_cut_evaluate_problem_1 import read_scene_a_config
        config_file = ROOT / 'data/raw/a/official/data/config.txt'
        config = read_evaluation_config(str(config_file))
        waits = read_scene_a_config(str(config_file))
        raw = args.graph.read_bytes()
        plan, details = construct(json.loads(raw), args.cores, config['capacity'],
                                  config['bandwidth'], waits['task_same_core_wait_cycles'])
    except Exception as error:
        args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
        with args.diagnostics.open('x') as stream:
            json.dump(getattr(error, 'response_probe_diagnostics', {
                'status': 'failed', 'stage': 'before_construct',
                'error_type': type(error).__name__, 'error': str(error),
                'calls': {'candidate_constructors': 0, 'E0': 0, 'E1': 0, 'E2': 0},
            }), stream, indent=2)
            stream.write('\n')
        raise
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        payload = (json.dumps(plan, separators=(',', ':')) + '\n').encode()
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    details['graph_sha256'] = hashlib.sha256(raw).hexdigest()
    details['plan_sha256'] = hashlib.sha256(payload).hexdigest()
    args.diagnostics.parent.mkdir(parents=True, exist_ok=True)
    with args.diagnostics.open('x') as stream:
        json.dump(details, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
