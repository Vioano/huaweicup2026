"""Research-only R5 same-partition phase experiment; never an E0 evaluator.

R5 proposal: AI chats/P1多Pipe链构造证明/附件/r5-P1_s6607_R5_causal_diagnosis/
src/proposed_real_work_phase.py. One official Task compilation is reused only for
plans with identical Task IDs, members and core ownership. Frozen official
_build_scene_a_tasks traverses sorted Task IDs and does not use core order to
build local Task bodies; both complete plans are validated before compilation.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import time

from src.q1.memory_packet_probe import MemoryFamily
from src.q1.capacity_return import author
from src.q1.compiled_memory_response import compile_plan
from src.q1.response_compile import _official_modules, UnsupportedResponse
from src.q1.response_oracle import simulate

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / 'AI chats/P1多Pipe链构造证明/附件/r5-P1_s6607_R5_causal_diagnosis/src/proposed_real_work_phase.py'


def pair_builder(*args, **kwargs):
    spec = importlib.util.spec_from_file_location('_r5_phase_proposal', PROPOSAL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.construct_pair(*args, **kwargs)


def validate_pair(graph, control, phase, cores, validator=None):
    if control['node_to_subgraph'] != phase['node_to_subgraph'] or len(control['core_schedules']) != cores or len(phase['core_schedules']) != cores:
        raise UnsupportedResponse('partition or core count changed')
    if any(set(a) != set(b) or len(a) != len(b) for a, b in zip(control['core_schedules'], phase['core_schedules'])):
        raise UnsupportedResponse('Task ownership changed')
    author.validate_plan_structure(graph, control)
    author.validate_plan_structure(graph, phase)
    validator = validator or _official_modules()[3]
    for plan in (control, phase):
        view = _official_modules()[1].derive_multicore_plan(graph, plan)
        validator.validate_task_order(view)
        if any(view['core_by_subgraph'][a] != view['core_by_subgraph'][b] for a, b in view['dependency_pairs']):
            raise UnsupportedResponse('cross-core compute Task dependency')


def _response_child(path, lines, gate):
    try:
        result = simulate(lines, gate, keep_trace=True)
        Path(path).write_text(json.dumps({'status': 'ok', 'result': result}, default=str))
    except Exception as error:
        Path(path).write_text(json.dumps({'status': 'error', 'error': f'{type(error).__name__}: {error}'}))


def timed_response(lines, gate, limit=30):
    """One isolated Fraction model call, with termination and no retry."""
    ctx = mp.get_context('spawn')
    with tempfile.TemporaryDirectory(prefix='p1-r5-fraction-') as tmp:
        result_path = Path(tmp)/'result.json'
        child = ctx.Process(target=_response_child, args=(str(result_path), lines, gate))
        began = time.perf_counter()
        child.start()
        try:
            child.join(max(0, limit - (time.perf_counter() - began)))
            if child.is_alive():
                child.kill(); child.join(5)
                raise TimeoutError('Fraction model exceeded 30 seconds')
            if child.exitcode != 0 or not result_path.exists():
                raise RuntimeError(f'Fraction child exited {child.exitcode} without result')
            if time.perf_counter() - began > limit:
                raise TimeoutError('Fraction model exceeded 30 seconds')
            record = json.loads(result_path.read_text())
            if record['status'] != 'ok':
                raise RuntimeError(record['error'])
            return record['result'], time.perf_counter()-began
        finally:
            if child.is_alive():
                child.kill(); child.join(5)


def run(graph, cores, capacity, bandwidth, gate, q, s, period, chain_work, threshold,
        *, family_factory=MemoryFamily, build_pair=pair_builder,
        validate=validate_pair, compiler=compile_plan, scorer=timed_response):
    if (type(cores) is not int or not 2 <= cores <= 5 or
        any(type(x) is not int or x <= 0 for x in (bandwidth, period, chain_work, threshold)) or
        type(gate) is not int or gate < 0 or
        type(q) is not int or q < 1 or type(s) is not int or not 1 <= s <= q or
        set(capacity) != {'L1', 'UB'} or any(type(x) is not int or x <= 0 for x in capacity.values())):
        raise ValueError('invalid explicit research parameters')
    stamp = time.perf_counter()
    account = {'Task_compile_attempted_upper_bound': 0, 'Task_compile_confirmed': 0,
               'Fraction_attempts': 0, 'E0': 0, 'E1': 0, 'E2': 0, 'retry': 0}
    report = {'status': 'unknown', 'source': 'R5 same-partition phase proposal',
              'proposal_sha256': hashlib.sha256(PROPOSAL.read_bytes()).hexdigest(),
              'parameters': dict(cores=cores, capacity=capacity, bandwidth=bandwidth,
                                 gate=gate, q=q, s=s, period=period,
                                 chain_work=chain_work, threshold=threshold),
              'calls': account, 'stage_wall_seconds': {}}
    control = phase = None
    stage = 'recognize'
    try:
        t = time.perf_counter()
        family = family_factory(graph, cores, capacity, bandwidth)
        chains = family.chains
        # MemoryFamily delegates to the frozen private-chain recognizer and
        # ordered descriptor proof. Check the exact original compute set again.
        compute = [op['id'] for op in graph['ops'] if op['op'] not in author.COPY]
        if len(compute) != len(set(compute)) or set(compute) != {u for c in chains for u in c} or sum(map(len, chains)) != len(compute):
            raise UnsupportedResponse('private chains do not cover all compute')
        if any(len(c) < 3 or family.view.ops[c[0]]['pipe'] != 'PIPE_M' or
               family.view.ops[c[-1]]['pipe'] != 'PIPE_M' or
               any(family.view.ops[u]['pipe'] != 'PIPE_V' for u in c[1:-1]) for c in chains):
            raise UnsupportedResponse('requires true M-V+-M chains')
        if any(sum(family.view.ops[u]['cycles'] for u in chain) != chain_work
               for chain in chains):
            raise UnsupportedResponse('declared chain work differs from original cycles')
        report['family_certificate'] = family.family_certificate
        report['stage_wall_seconds']['recognize'] = time.perf_counter()-t
        stage = 'plan_and_validation'
        t = time.perf_counter()
        control, phase, info = build_pair(family.bins, q=q, s=s,
            body_period=period, chain_compute_work=chain_work,
            compute_ids_in_input_order=compute, max_tasks_per_core_budget=12)
        task_count = sum(map(len, control['core_schedules']))
        if task_count > 12*cores or any(len(line) > 12 for line in control['core_schedules']):
            raise UnsupportedResponse('12K Task budget exceeded')
        validate(graph, control, phase, cores)
        report['plans_validated'] = True
        report['proposal'] = info
        report['task_count'] = task_count
        report['stage_wall_seconds']['plan_and_validation'] = time.perf_counter()-t
        stage = 'compile_once'
        t = time.perf_counter()
        account['Task_compile_attempted_upper_bound'] = task_count
        lines, certificate = compiler(graph, control, capacity, bandwidth)
        account['Task_compile_confirmed'] = task_count
        report['stage_wall_seconds']['compile_once'] = time.perf_counter()-t
        by_id = {}
        for order, line in zip(control['core_schedules'], lines):
            if len(order) != len(line):
                raise UnsupportedResponse('compiled Task count mismatch')
            for task_id, task in zip(order, line):
                if task_id in by_id or task.task_id != task_id:
                    raise UnsupportedResponse('compiled Task ID mismatch')
                by_id[task_id] = task
        if len(by_id) != task_count:
            raise UnsupportedResponse('compiled Task coverage mismatch')
        phase_lines = [[by_id[task_id] for task_id in order] for order in phase['core_schedules']]
        report['signatures'] = {str(i): repr(task.signature()) for i, task in sorted(by_id.items())}
        report['scheduled_copy_bytes'] = certificate['traffic']['scheduled_copy_bytes']
        report['compile_certificate'] = certificate
        report['compiled_ports'] = {str(i): [
            [dict(work=op.work, ddr=op.ddr, need=list(op.need), original_id=op.original_id)
             for op in port] for port in task.ports]
            for i, task in sorted(by_id.items())}
        for name, model_lines in (('control', lines), ('phase', phase_lines)):
            stage = name+'_Fraction'
            t = time.perf_counter()
            account['Fraction_attempts'] += 1
            result, wall = scorer(model_lines, gate, 30)
            report['stage_wall_seconds'][name+'_Fraction'] = wall
            report[name+'_model'] = result
        report['phase_better'] = report['phase_model']['makespan'] < report['control_model']['makespan']
        report['suggest_independent_E0'] = bool(report['phase_better'] and report['phase_model']['makespan'] < threshold)
        report['status'] = 'model_pair_complete_NOT_E0'
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
        report['failed_stage'] = stage
        report['stage_wall_seconds'][stage+'_attempt'] = time.perf_counter()-t
    report['total_wall_seconds'] = time.perf_counter()-stamp
    return control, phase, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('graph', type=Path)
    p.add_argument('--cores', type=int, required=True)
    p.add_argument('--capacity-l1', type=int, required=True)
    p.add_argument('--capacity-ub', type=int, required=True)
    p.add_argument('--bandwidth', type=int, required=True)
    p.add_argument('--gate', type=int, required=True)
    for name in ('q', 's', 'period', 'chain-work', 'threshold'):
        p.add_argument('--'+name, type=int, required=True)
    p.add_argument('--expect-graph-sha256', required=True)
    p.add_argument('--output-root', type=Path, required=True)
    p.add_argument('--execute', action='store_true', required=True)
    a = p.parse_args()
    if a.output_root.exists():
        p.error('output directory already exists')
    raw = a.graph.read_bytes();digest = hashlib.sha256(raw).hexdigest()
    if digest != a.expect_graph_sha256:
        p.error('graph SHA-256 differs from declared input')
    a.output_root.mkdir(parents=True, exist_ok=False)
    control, phase, report = run(json.loads(raw), a.cores,
        {'L1':a.capacity_l1,'UB':a.capacity_ub}, a.bandwidth, a.gate,
        a.q,a.s,a.period,a.chain_work,a.threshold)
    report['graph_sha256'] = digest
    verified = report.get('plans_validated') is True
    for name, obj in (('diagnostics.json',report),
                      ('control-plan.json',control if verified else None),
                      ('phase-plan.json',phase if verified else None)):
        if obj is not None:
            (a.output_root/name).write_text(json.dumps(obj, separators=(',', ':'), default=str)+'\n')
    if report['status'] != 'model_pair_complete_NOT_E0':
        raise SystemExit(2)

if __name__ == '__main__':
    main()
