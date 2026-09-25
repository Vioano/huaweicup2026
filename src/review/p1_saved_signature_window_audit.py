"""Independent static audit of the archived R5 fixed-signature certificate.

Reads JSON only. It does not import the model, compile Tasks, or simulate.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAIRS = ROOT / 'results/a/p1-period7-colab-20260925/run-0534Z/paired-signatures.json'
CERT = ROOT / 'AI chats/P1多Pipe链构造证明/附件/r5-P1_s6607_R5_causal_diagnosis/results/causal_certificates.json'
PAIRS_SHA256 = '2a90a5b0e8b3ff19fe88a07e6580dc4899a63b7654d0d268c0941b947549c95b'
PIPES = ('PIPE_M', 'PIPE_V', 'PIPE_MTE2', 'PIPE_MTE3')


def graph(task, orbit):
    ops = {(p, j): row for p, port in enumerate(task['ports'])
           for j, row in enumerate(port, 1)}
    before = {}
    after = {key: set() for key in ops}
    duration = {key: op[0] * (orbit if op[1] else 1)
                for key, op in ops.items()}
    for (p, j), op in ops.items():
        assert len(op[2]) == 4 and op[0] > 0 and type(op[1]) is bool
        req = {(q, rank) for q, rank in enumerate(op[2]) if rank}
        if j > 1:
            req.add((p, j - 1))
        assert req <= ops.keys(), (task['task_id'], p, j, req - ops.keys())
        before[p, j] = req
        for u in req:
            after[u].add((p, j))
    pending = {key: len(req) for key, req in before.items()}
    ready = sorted(key for key, n in pending.items() if n == 0)
    finish = {}
    order = []
    while ready:
        u = ready.pop(0)
        finish[u] = duration[u] + max((finish[v] for v in before[u]), default=0)
        order.append(u)
        for v in sorted(after[u]):
            pending[v] -= 1
            if pending[v] == 0:
                ready.append(v)
        ready.sort()
    assert len(order) == len(ops), ('cycle', task['task_id'])
    tail = {}
    for u in reversed(order):
        tail[u] = max((duration[v] + tail[v] for v in after[u]), default=0)
    jobs = {(PIPES[p], j): (finish[p, j] - duration[p, j],
                           duration[p, j], tail[p, j])
            for (p, j), op in ops.items() if op[1]}
    return max(finish.values(), default=0), jobs


def audit(name, variant, cert, gate):
    tasks = {t['task_id']: t for t in variant['tasks']}
    lines = variant['core_schedules']
    flat = sum(lines, [])
    assert len(flat) == len(set(flat)), (name, 'duplicate scheduled Task')
    assert len(tasks) == len(variant['tasks']), (name, 'duplicate Task definition')
    assert len(lines) == 5 and set(tasks) == set(sum(lines, []))
    assert all(tasks[t]['core'] == c for c, line in enumerate(lines) for t in line)
    common = 0
    while common < min(map(len, lines)) and all(
            tasks[line[common]]['ports'] == tasks[lines[0][common]]['ports']
            for line in lines):
        common += 1
    assert all(len(line) - common <= 1 for line in lines)
    groups = {}
    for c, line in enumerate(lines):
        if len(line) > common:
            sig = json.dumps(tasks[line[common]]['ports'], separators=(',', ':'))
            groups.setdefault(sig, []).append(c)
    orbit = {t: 5 for line in lines for t in line[:common]}
    for cs in groups.values():
        for c in cs:
            orbit[lines[c][common]] = len(cs)
    task_bounds = {}
    rows = []
    checked_jobs = 0
    for tid, task in sorted(tasks.items()):
        entry = cert['tasks'][str(tid)]
        assert entry['orbit_size'] == orbit[tid]
        cp, jobs = graph(task, orbit[tid])
        assert entry['critical_path_bound'] == cp
        win = entry['ddr_window']
        if win is None:
            assert not jobs
            window = 0
            chosen = {}
        else:
            rv, qv = win['release_threshold'], win['tail_threshold']
            chosen = {key: (r, d, q) for key, (r, d, q) in jobs.items()
                      if r >= rv and q >= qv}
            reported = {(row['op'][0], row['op'][1]):
                        (row['r'], row['d'], row['q']) for row in win['jobs']}
            assert chosen == reported and len(reported) == len(win['jobs']), (name, tid, 'jobs')
            service = sum(d for r, d, q in chosen.values())
            window = rv + service + qv
            assert service == win['service'] and window == win['bound']
            checked_jobs += len(chosen)
        task_bounds[tid] = max(cp, window)
        assert entry['bound'] == task_bounds[tid]
        rows.append({'task': tid, 'orbit': orbit[tid], 'critical_path': cp,
                     'window': window, 'selected_jobs': len(chosen), 'bound': task_bounds[tid]})
    per_core = {str(c): sum(task_bounds[t] for t in line) + gate * max(0, len(line) - 1)
                for c, line in enumerate(lines)}
    lower = max(per_core.values())
    assert per_core == cert['per_core_bounds']
    assert lower == cert['fixed_plan_lower_bound']
    assert lower == {'whole_seed': 101836, 'period7_seed': 106071}[name]
    assert lower <= variant['expected_model_makespan']
    return {'common_rounds': common, 'tail_groups': sorted(groups.values()),
            'checked_selected_ddr_jobs': checked_jobs, 'per_core': per_core,
            'lower_bound': lower, 'saved_model_makespan': variant['expected_model_makespan'],
            'tasks': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True,
                        help='explicit result JSON path; existing files are not overwritten')
    args = parser.parse_args()
    assert hashlib.sha256(PAIRS.read_bytes()).hexdigest() == PAIRS_SHA256
    pairs = json.loads(PAIRS.read_text())
    certs = json.loads(CERT.read_text())
    assert pairs['gate'] == 100
    assert tuple(pairs['pipes']) == PIPES and set(pairs['variants']) == set(certs)
    result = {'scope': 'saved compiled signatures under rational shared-DDR model only',
              'input_sha256': hashlib.sha256(PAIRS.read_bytes()).hexdigest(),
              'certificate_sha256': hashlib.sha256(CERT.read_bytes()).hexdigest(),
              'variants': {name: audit(name, variant, certs[name], pairs['gate'])
                           for name, variant in pairs['variants'].items()}}
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({name: {'lower': row['lower_bound'], 'checked_jobs':
                             row['checked_selected_ddr_jobs']}
                      for name, row in result['variants'].items()}))


if __name__ == '__main__':
    main()
