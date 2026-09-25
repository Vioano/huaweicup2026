"""Static bounds only, no solver imports, plan construction or evaluation."""
from collections import defaultdict, Counter
from pathlib import Path
import hashlib
import json
import math
import zipfile

ROOT = Path(__file__).resolve().parents[3]
with zipfile.ZipFile(ROOT / 'data/raw/a/official-cases.zip') as z:
    raw = z.read('data/case_044.json')
g = json.loads(raw)
ops = {o['id']: o for o in g['ops'] if o['op'] not in {'COPY_IN', 'COPY_OUT'}}
ts = {t['id']: t for t in g['tensors']}
ps, cs, adj = defaultdict(set), defaultdict(set), defaultdict(set)
for e in g['edges']:
    u, v = e['source'], e['target']
    if u in ops and v in ts:
        ps[v].add(u)
    elif u in ts and v in ops:
        cs[u].add(v)
    elif u in ops and v in ops:
        adj[u].add(v)
        adj[v].add(u)
for t in ts:
    for u in ps[t]:
        for v in cs[t]:
            adj[u].add(v)
            adj[v].add(u)
left = set(ops)
components = []
while left:
    first = min(left)
    left.remove(first)
    todo, nodes = [first], {first}
    while todo:
        u = todo.pop()
        for v in adj[u] & left:
            left.remove(v)
            nodes.add(v)
            todo.append(v)
    components.append(nodes)
ext = {t for t in ts if cs[t] and not ps[t]}
inputs = [{t for t in ext if cs[t] & ns} for ns in components]
common = set.intersection(*inputs)
union = set.union(*inputs)
private_incidence = Counter(t for ss in inputs for t in ss - common)
work = [sum(ops[u]['cycles'] for u in ns if ops[u]['pipe'] == 'PIPE_M') for ns in components]
assert len(set(work)) == 1
assert all(n == 1 for n in private_incidence.values())
shared_bytes = sum(ts[t]['size'] for t in common)
private_bytes = sum(ts[t]['size'] for t in union-common)
shared_service = sum(max(1, math.ceil(ts[t]['size']/60)) for t in common)
private_service = sum(max(1, math.ceil(ts[t]['size']/60)) for t in union-common)
rows = []
for r in range(1, 6):
    compute_lb = math.ceil(len(components)/r) * work[0]
    read_lb = r*shared_service + private_service
    rows.append({'active_cores': r, 'compute_lb': compute_lb,
                 'mandatory_external_bytes_lb': r*shared_bytes+private_bytes,
                 'DDR_lb': read_lb, 'joint_lb': max(compute_lb, read_lb)})
out = {'graph_sha256': hashlib.sha256(raw).hexdigest(),
       'scope': '044 conditional on each compute component staying on one core; Task splitting on that core allowed. Not a global P1 bound.',
       'component_count': len(components), 'M_work_per_component': work[0],
       'common_input_tensor_count': len(common), 'common_input_bytes': shared_bytes,
       'private_input_unique_bytes': private_bytes, 'all_noncommon_inputs_private': True,
       'common_service_cycles': shared_service, 'private_service_cycles': private_service,
       'rows': rows, 'conditional_M_lb': min(row['joint_lb'] for row in rows),
       'new_solver_Task_E0_E1_E2_calls': 0,
       'limitations': ['Condition is that each static component remains on one core. Cross-component dependencies can only further restrict feasible schedules, so are not relaxed into an achievable construction.',
                       'Shared global bandwidth60 and no P1 cross-Task persistent input cache are official premises.',
                       'Ignores output/cut traffic, gates, memory, precedence, and pipeline idle; not an achievable schedule.']}
Path(__file__).with_name('conditional-bound.json').write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps(out, indent=2))
