"""Opt-in bounded research probe for ordered private P1 MEM packet families.

Search proves only the scalar response model. Publication requires a separate
original-ID full-plan compile and exact response replay; never an E0 claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import signal
import time

from src.q1.memory_packet_probe import MemoryFamily, Kernel, ROOT
from src.q1.compiled_memory_response import compile_plan
from src.q1.capacity_return import author
from src.q1.response_compile import UnsupportedResponse
from src.q1.response_oracle import simulate
from src.review.p1_return_cut_resource_bound import graph_resources
from src.review.p1_packet_edge_bound import Resources
from src.review.p1_lazy_packet_search import search, UnknownResult, Unknown
from src.review.p1_packet_seed import choose_return_seed
from src.review.p1_memory_key_contract import source_scope

SOURCES = ("src/review/p1_lazy_memory_probe.py", "src/review/p1_lazy_packet_search.py",
           "src/review/p1_packet_edge_bound.py", "src/review/p1_return_cut_resource_bound.py",
           "src/review/p1_packet_seed.py")


def hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def charge(kind, n, nonempty, makespan, gate):
    if not nonempty:
        return 0
    return makespan + gate - (gate if (kind == "normal" and n == 0 or
                                         kind == "terminal" and n == 0) else 0)


def accounting(kernel):
    known = kernel.completed + (kernel.full_confirmed or 0)
    return dict(task_compile_attempts_reserved=kernel.compiles,
                task_compile_confirmed_completed=(known if known == kernel.compiles else None),
                task_compile_confirmed_lower_bound=known,
                final_task_attempts_reserved=kernel.full_reserved,
                response_attempts=kernel.response_attempts,
                response_confirmed_completed=kernel.response_completed)


def publish(output, report, plan):
    """Publish a receipt before its plan; consumers require both and their hash.

    A crash before the last rename can leave a receipt without a plan, never a
    visible plan without its verified receipt. It is not a completed delivery.
    """
    plan_tmp, report_tmp = output/'plan.json.tmp', output/'report.json.tmp'
    try:
        if report['status'] == 'verified_model' and plan is not None:
            raw = (json.dumps(plan, separators=(',', ':'))+'\n').encode()
            plan_tmp.write_bytes(raw)
            report['plan_sha256'] = hashlib.sha256(raw).hexdigest()
        else:
            plan = None
        report_tmp.write_text(json.dumps(report, default=str, indent=2)+'\n')
        report_tmp.replace(output/'report.json')
        if plan is not None:
            plan_tmp.replace(output/'plan.json')
    except BaseException:
        (output/'plan.json').unlink(missing_ok=True)
        raise
    finally:
        plan_tmp.unlink(missing_ok=True)
        report_tmp.unlink(missing_ok=True)


def guard(f):
    v = f.view
    for chain in f.chains:
        if (len(chain) < 3 or v.ops[chain[-2]]['pipe'] != 'PIPE_V' or
                v.ops[chain[-1]]['pipe'] != 'PIPE_M' or
                not (v.out_t[chain[-2]] & v.in_t[chain[-1]])):
            raise UnsupportedResponse("last V output is not consumed by last M")
        if any(f.has_out[tid] for u in chain[:-1] for tid in v.out_t[u]):
            raise UnsupportedResponse("interior original output tap invalidates W-first bound")


class BoundedKernel(Kernel):
    def __init__(self, family, gate, compile_limit, response_limit, deadline):
        super().__init__(family, gate, compile_limit, deadline)
        self.response_limit = response_limit
        self.response_attempts = self.response_completed = 0
        self.full_reserved = 0
        self.full_confirmed = 0

    def check(self):
        if time.perf_counter() >= self.deadline:
            raise UnknownResult("wall budget expired")

    def get(self, nodes):
        if tuple(nodes) not in self.tasks and self.compiles >= self.limit:
            raise UnknownResult("Task compile budget exhausted")
        try:
            return super().get(nodes)
        except RuntimeError as error:
            # Original Kernel raises RuntimeError for its budget. Do not turn
            # any other runtime failure into a proved unsupported edge.
            if str(error) == '2500 Task compilation limit':
                raise UnknownResult(str(error)) from error
            raise

    def response(self, lines):
        self.check()
        if self.response_attempts >= self.response_limit:
            raise UnknownResult("Fraction response budget exhausted")
        self.response_attempts += 1
        try:
            result = simulate(lines, self.gate)
        except RuntimeError as error:
            if str(error) == 'response event budget exhausted':
                raise UnknownResult(str(error)) from error
            raise
        self.response_completed += 1
        self.check()
        return result

    def profile(self, n, r, q, s, drain=False):
        groups = [self.f.members(k, n, r, q, s) for k in range(self.f.cores)]
        try:
            items = [self.get(nodes) for nodes in groups]
        except UnsupportedResponse as error:
            self.rejected.append({"edge": [n, r, q, s], "reason": str(error)})
            return None
        signatures = [item['task'].signature() for item in items]
        if len(set(map(repr, signatures))) != 1:
            self.rejected.append({"edge": [n, r, q, s], "reason": "per-core signatures differ"})
            return None
        key = tuple(signatures)
        if key not in self.responses:
            try:
                self.responses[key] = self.response([[item['task']] for item in items])
            except UnsupportedResponse as error:
                self.rejected.append({"edge": [n, r, q, s], "reason": str(error)})
                return None
        cost = charge('drain' if drain else 'normal', n, True,
                      self.responses[key]['makespan'], self.gate)
        return dict(cost=cost, groups=groups, signatures=signatures,
                    bytes=sum(item['bytes'] for item in items))

    def suffix(self, r, policy):
        f = self.f
        groups, lines, traffic = [], [], 0
        for k in range(f.cores):
            old = f.members(k, f.B, r, 0, 0) if r else []
            rest = [u for chain in f.bins[k][f.B:] for u in chain]
            parts = ([old + rest] if old or rest else []) if policy == 'merge' else [x for x in (old, rest) if x]
            try:
                items = [self.get(nodes) for nodes in parts]
            except UnsupportedResponse as error:
                self.rejected.append({"terminal": [r, policy, k], "reason": str(error)})
                return None
            groups.append(parts)
            lines.append([item['task'] for item in items])
            traffic += sum(item['bytes'] for item in items)
        nonempty = any(lines)
        try:
            model = self.response(lines) if nonempty else {'makespan': 0}
        except UnsupportedResponse as error:
            self.rejected.append({"terminal": [r, policy], "reason": str(error)})
            return None
        return dict(cost=charge('terminal', f.B, nonempty, model['makespan'], self.gate),
                    groups=groups, bytes=traffic)


def verify_final(graph, plan, expected, expected_bytes, upper, kernel, capacity, bandwidth,
                 total_limit, compiler=compile_plan,
                 validator=author.validate_plan_structure):
    validator(graph, plan)
    kernel.check()
    count = sum(map(len, plan['core_schedules']))
    if kernel.compiles + count > total_limit:
        raise UnknownResult("final Task reservation exceeds compile budget")
    kernel.full_reserved = count
    kernel.compiles += count  # a failed compile may have completed an unknown prefix
    kernel.full_confirmed = None
    lines, cert = compiler(graph, plan, capacity, bandwidth)
    kernel.full_confirmed = count
    if [[t.signature() for t in line] for line in lines] != expected:
        raise UnsupportedResponse("final Task signatures differ")
    if cert['traffic']['scheduled_copy_bytes'] != expected_bytes:
        raise UnsupportedResponse("final DDR bytes differ")
    if kernel.response(lines)['makespan'] != upper:
        raise UnsupportedResponse("final scalar response differs")
    return cert


def construct(graph, cores, capacity, bandwidth, gate, *, task_limit, final_max_tasks,
              response_limit, oracle_limit, expansion_limit, seconds,
              family_factory=MemoryFamily, kernel_factory=BoundedKernel, state=None):
    if (type(cores) is not int or not 1 <= cores <= 5 or
            set(capacity) != {'L1', 'UB'} or
            any(type(v) is not int or v <= 0 for v in capacity.values()) or
            type(bandwidth) is not int or bandwidth <= 0 or
            type(gate) is not int or gate < 0):
        raise ValueError('positive capacities/bandwidth, cores 1..5 and nonnegative gate required')
    if (not 1 <= task_limit <= 2500 or not 1 <= final_max_tasks <= task_limit or
            not 1 <= response_limit <= 512 or not 1 <= oracle_limit <= 512 or
            not 1 <= expansion_limit <= 100000 or not 0 < seconds <= 60):
        raise ValueError("explicit bounded budgets required")
    start = time.perf_counter()
    family = family_factory(graph, cores, capacity, bandwidth)
    guard(family)
    resources = Resources(**graph_resources(graph, cores, bandwidth), gate=gate)
    kernel = kernel_factory(family, gate, task_limit-final_max_tasks,
                            response_limit-1, start + seconds)
    if state is not None:
        state['kernel'] = kernel
    edges = {}
    precomputed = {}

    def exact(kind, state, payload):
        key = (kind, state, payload)
        if key in precomputed:
            return precomputed[key]
        n, r = state
        edge = kernel.suffix(r, payload) if kind == 'terminal' else kernel.profile(
            n, r, *(payload if kind == 'normal' else (0, 0)), drain=kind == 'drain')
        if edge is not None:
            edges[kind, state, payload] = edge
        return None if edge is None else edge['cost']

    def bound(kind, state, prefix, payload):
        n, r = state
        if kind == 'box':
            return resources.box(n, r, payload, prefix_end=prefix)['frontier_lower_bound']
        largest = max(resources.counts)-n
        total = sum(resources.counts)-len(resources.counts)*n
        tail = max(largest*(resources.a+resources.c)+r*resources.c,
                   largest*resources.b,
                   total*resources.d_whole+len(resources.counts)*r*resources.d_return)
        return prefix + tail

    # A structural seed is attempted once; it is not an E0-derived incumbent.
    # Its queries count against the same oracle/compile/response budgets.
    seed = dict(status='not_attempted', oracle_calls=0)
    incumbent = None
    if state is not None:
        state['seed'] = seed
    if family.B and oracle_limit >= 2:
        seed['selection'] = choose_return_seed(resources, family.B)
        s = seed['selection']['s']
        seed_path = (('normal', (0, 0), (family.B, s)),
                     ('terminal', (family.B, s), 'merge'))
        total = 0
        for action in seed_path:
            seed['oracle_calls'] += 1
            try:
                value = exact(*action)
            except (UnknownResult, TimeoutError) as error:
                value = Unknown
                seed['error'] = f'{type(error).__name__}: {error}'
            precomputed[action] = value
            if value is Unknown or value is None:
                seed['status'] = 'unknown' if value is Unknown else 'unsupported'
                break
            total += value
        else:
            incumbent = (total, seed_path)
            seed.update(status='model_candidate', upper=total, path=seed_path)

    result = search(family.B, exact, bound, oracle_limit-seed['oracle_calls'],
                    incumbent=incumbent,
                    max_expansions=expansion_limit,
                    should_stop=lambda: time.perf_counter() >= kernel.deadline)
    if state is not None:
        state['scalar'] = result
    if result['best_path'] is None:
        raise UnknownResult("scalar search found no candidate within budgets")
    mapping, orders, expected = {}, [[] for _ in range(cores)], [[] for _ in range(cores)]
    selected_groups = []
    predicted_bytes = 0
    for action in result['best_path']:
        kind, state, payload = action
        edge = edges[action]
        groups = edge['groups']
        predicted_bytes += edge['bytes']
        for k, parts in enumerate(groups if kind == 'terminal' else [[g] for g in groups]):
            for nodes in parts:
                item = kernel.tasks[tuple(nodes)]
                task_id = sum(map(len, orders))
                selected_groups.append(dict(task_id=task_id, core=k, nodes=list(nodes),
                                            signature=repr(item['task'].signature()),
                                            scheduled_copy_bytes=item['bytes']))
                orders[k].append(task_id)
                expected[k].append(item['task'].signature())
                for u in nodes:
                    if u in mapping:
                        raise UnsupportedResponse("duplicate compute member")
                    mapping[u] = task_id
    count = sum(map(len, orders))
    if count > final_max_tasks:
        raise UnknownResult("selected plan exceeds reserved final Task count")
    kernel.check()
    plan = {'node_to_subgraph': {str(op['id']): mapping[op['id']]
                                 for op in graph['ops'] if op['op'] not in author.COPY},
            'core_schedules': orders}
    kernel.response_limit = response_limit  # release the one reserved replay
    cert = verify_final(graph, plan, expected, predicted_bytes, result['upper'], kernel,
                        capacity, bandwidth, task_limit)
    return plan, dict(kind='lazy-memory-research-NOT-E0', scalar=result, seed=seed,
                      **accounting(kernel),
                      full_plan_tasks=count, selected_groups=selected_groups,
                      predicted_scheduled_copy_bytes=predicted_bytes,
                      certificate=cert, global_optimal=False,
                      p1_optimal=False, e0_optimal=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph', type=Path)
    p.add_argument('--cores', type=int, required=True)
    p.add_argument('--capacity-l1', type=int, required=True)
    p.add_argument('--capacity-ub', type=int, required=True)
    p.add_argument('--bandwidth', type=int, required=True)
    p.add_argument('--gate', type=int, required=True)
    for name in ('task-limit', 'final-max-tasks', 'response-limit', 'oracle-limit',
                 'expansion-limit', 'seconds'):
        p.add_argument('--'+name, type=int, required=True)
    p.add_argument('--output-root', type=Path, required=True)
    p.add_argument('--execute', action='store_true', required=True)
    a = p.parse_args()
    if not 0 < a.seconds <= 60:
        p.error('--seconds must be in 1..60')
    if not a.execute or a.output_root.exists():
        raise SystemExit('explicit --execute and fresh output directory required')
    before = hashes()
    official_before = source_scope({'L1': a.capacity_l1, 'UB': a.capacity_ub}, a.bandwidth)
    output = a.output_root
    output.mkdir(parents=True, exist_ok=False)
    graph_raw = a.graph.read_bytes()
    report = dict(status='unknown', source_scope=before, global_optimal=False,
                  p1_optimal=False, e0_optimal=False,
                  official_source_scope=official_before,
                  graph_sha256=hashlib.sha256(graph_raw).hexdigest(),
                  cores=a.cores, capacity={'L1': a.capacity_l1, 'UB': a.capacity_ub},
                  bandwidth=a.bandwidth, gate=a.gate,
                  budgets=dict(task_limit=a.task_limit, final_max_tasks=a.final_max_tasks,
                               response_limit=a.response_limit, oracle_limit=a.oracle_limit,
                               expansion_limit=a.expansion_limit, seconds=a.seconds))
    state = {}
    plan = None
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if previous_timer[0]:
        raise RuntimeError('existing process alarm; cannot own 60-second bound')
    def expired(_signum, _frame):
        raise UnknownResult('wall alarm expired')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, a.seconds)
    try:
        plan, info = construct(json.loads(graph_raw), a.cores,
                               {'L1': a.capacity_l1, 'UB': a.capacity_ub}, a.bandwidth,
                               a.gate, task_limit=a.task_limit, final_max_tasks=a.final_max_tasks,
                               response_limit=a.response_limit, oracle_limit=a.oracle_limit,
                               expansion_limit=a.expansion_limit, seconds=a.seconds,
                               state=state)
        if hashes() != before or source_scope({'L1': a.capacity_l1, 'UB': a.capacity_ub}, a.bandwidth) != official_before:
            raise UnknownResult('source changed during construction')
        report.update(status='verified_model', **info)
    except Exception as error:
        report['status'] = 'unknown'
        report['error'] = f'{type(error).__name__}: {error}'
        plan = None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
    kernel = state.get('kernel')
    if 'scalar' in state:
        report['scalar'] = state['scalar']
    if 'seed' in state:
        report['seed'] = state['seed']
    if kernel is not None:
        report.update(accounting(kernel))
    try:
        report['source_scope_after'] = hashes()
        report['source_scope_unchanged'] = report['source_scope_after'] == before
    except Exception as error:
        report['source_scope_unchanged'] = False
        report['source_scope_error'] = f'{type(error).__name__}: {error}'
    try:
        report['official_source_scope_after'] = source_scope(
            {'L1': a.capacity_l1, 'UB': a.capacity_ub}, a.bandwidth)
        report['official_scope_unchanged'] = report['official_source_scope_after'] == official_before
    except Exception as error:
        report['official_scope_unchanged'] = False
        report['official_scope_error'] = f'{type(error).__name__}: {error}'
    if not report['source_scope_unchanged'] or not report['official_scope_unchanged']:
        report['status'] = 'unknown'
        plan = None
    publish(output, report, plan)
    if report['status'] != 'verified_model' or plan is None:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
