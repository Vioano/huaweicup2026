"""Three declared static Task compilations; no solver or evaluator execution."""
import argparse
import hashlib
import json
from pathlib import Path
import signal
import sys
import time
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    from src.q1.variable_packet import Family, digest
    from src.q1.compiled_memory_response import compile_plan
    cap = {'L1': 524288, 'UB': 131072}
    archive_path = repo / 'data/raw/a/official-cases.zip'
    with zipfile.ZipFile(archive_path) as archive:
        raw = archive.read('data/case_008.json')
    family = Family(json.loads(raw), 5, cap, 60)
    out = Path(__file__).resolve().parent
    result = dict(kind='static-real-projection-not-E0', case='008', cores=5,
                  input_sha256=hashlib.sha256(raw).hexdigest(),
                  source_hashes={p:hashlib.sha256((repo/p).read_bytes()).hexdigest()
                                 for p in ['src/q1/compiled_memory_response.py',
                                           'src/q1/variable_packet.py', 'src/q1/packet_dp.py']},
                  capacity=cap, bandwidth=60, declared_profiles=[[0,2,0],[0,2,2],[1,2,2]],
                  max_task_compiles=3, task_compiles=0, calls={'solver':0,'E0':0,'E1':0,'E2':0},
                  rows=[])
    started = time.monotonic()
    def timeout(*_):
        raise TimeoutError('60-second probe deadline')
    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, 60)
    for r,q,s in result['declared_profiles']:
        nodes = family.members(0,r,r,q,s)
        graph = family.projection.graph(nodes)
        plan = dict(node_to_subgraph={str(u):0 for u in nodes}, core_schedules=[[0]])
        row = dict(r=r,q=q,s=s, nodes=nodes, conservative_footprint=family.footprint(nodes),
                   conservative_fits=family.fits(r,q,s))
        before = time.monotonic()
        result['task_compiles'] += 1
        try:
            lines, cert = compile_plan(graph, plan, cap, 60)
            prefix = f'r{r}-q{q}-s{s}'
            (out/(prefix+'-certificate.json')).write_text(json.dumps(cert,indent=2)+'\n')
            task = lines[0][0]
            row.update(status='compiled', signature_sha256=digest(task.signature()),
                       tasks=cert['tasks'], traffic=cert['traffic'], certificate=prefix+'-certificate.json')
        except Exception as exc:
            row.update(status='rejected', reason=f'{type(exc).__name__}: {exc}')
        row['wall_seconds'] = time.monotonic()-before
        result['rows'].append(row)
        (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
        if row['status'] != 'compiled':
            break
    signal.setitimer(signal.ITIMER_REAL,0)
    result['wall_seconds'] = time.monotonic()-started
    (out/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
