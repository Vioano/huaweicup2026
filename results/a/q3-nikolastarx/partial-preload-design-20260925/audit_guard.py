"""Read saved Task graphs to test the single-activation model; no official imports."""
from collections import defaultdict
from pathlib import Path
import gzip
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / 'results/a/q3-nikolastarx/pipeline-prefix-static-20260925/snapshots.json.gz'


def main():
    raw = SOURCE.read_bytes()
    data = json.loads(gzip.decompress(raw))
    rows = []
    for key, task in data['candidate'].items():
        c = int(key)
        if c == 0:
            continue  # R6 keeps core zero singleton; no merged pilot stage.
        ops = {o['id']: o for o in task['graph']['ops']}
        compute = {u for u, o in ops.items() if o['op'] not in {'COPY_IN', 'COPY_OUT'}}
        sg = task['subgraph_order'][0]
        pilot = [u for u in task['pre_step2_word']
                 if u in compute and task['op_subgraph'][str(u)] == sg]
        assert len(pilot) > 1
        rank = {u:i for i,u in enumerate(pilot)}
        out, cons = defaultdict(set), defaultdict(set)
        for edge in task['graph']['edges']:
            u, v = edge['source'], edge['target']
            if u in ops:
                out[u].add(v)
            elif v in ops:
                cons[u].add(v)
        gates = []
        for link in data['cross_links']:
            if link['target_core'] != c:
                continue
            copy = link['target_copy_in_id']
            readers = {v for tid in out[copy] for v in cons[tid] if v in rank}
            if readers:
                gates.append({'copy_id':copy, 'source_core':link['source_core'],
                              'size_bytes':link['size'],
                              'pilot_first_consumer_index':min(rank[v] for v in readers)})
        rows.append({'core':c, 'pilot_compute_ops':len(pilot), 'cross_activation_count':len(gates),
                     'cross_activations':gates,
                     'single_head_activation_guard':len(gates)==1 and gates[0]['pilot_first_consumer_index']==0})
    report = {'scope':'saved R6 044 Task graph, not a new plan, model score or official execution',
              'source':str(SOURCE.relative_to(ROOT)), 'source_sha256':hashlib.sha256(raw).hexdigest(),
              'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'stages':rows, 'calls':{'Task':0,'Step1':0,'Step2':0,'Step3':0,'E0':0,'solver':0},
              'implication':'The single-activation formula only applies to stages whose guard is true; otherwise interior releases require additional state.'}
    (HERE/'guard-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(rows,indent=2))


if __name__ == '__main__':
    main()
