"""Static resident-flow capacity certificate; never builds a plan or scores."""
import hashlib
import json
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q3.construct import Index
from src.q3.attention_rows import _ports, _recognize
from src.q3.query_flow import _decompose

DIR = Path(__file__).resolve().parent
EXPECTED = {
    'src/q3/query_flow.py': '88aca80c6e5dac46e56a6894a165e40aab7e21ac68db66b6dac83539a1d2d2f0',
    'src/q3/attention_rows.py': 'a4076188bda3037cdaa22686bf85d20051a3d8020e02d78d46db36adc5c10bb9',
    'src/q3/construct.py': '942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73',
    'data/raw/a/official/data/config.txt': 'dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9',
    'data/raw/a/official/data/case_005.json': 'c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f',
    'data/raw/a/official/data/case_086.json': 'ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a',
}


def alarm(_signum, _frame):
    raise TimeoutError('30-second total wall alarm')


def one(case, capacity):
    graph = json.loads((ROOT / f'data/raw/a/official/data/case_{case}.json').read_text())
    index = Index(graph)
    ports = _ports(index)
    label, keys, _rows = _decompose(index, ports, _recognize(index, ports))
    r = len(keys)
    if r > 12:
        raise ValueError(f'case {case}: r={r}>12; frozen stop rule')
    if r == 0:
        raise ValueError(f'case {case}: empty flow decomposition')
    support = [{pool: set() for pool in capacity} for _ in range(r)]
    for tid, tensor in ports.tensors.items():
        pool = 'UB' if tensor['pos'] == 'DDR' else tensor['pos']
        if pool not in capacity or type(tensor['size']) is not int or tensor['size'] < 0:
            raise ValueError(f'case {case}: invalid physical tensor {tid}')
        touched = ports.consumers[tid] | {ports.producer.get(tid)}
        flows = {label[u][1] for u in touched if u in label and label[u][0] != 'S'}
        for flow in flows:
            support[flow][pool].add(tid)

    singleton = [{pool: sum(ports.tensors[t]['size'] for t in support[i][pool])
                  for pool in capacity} for i in range(r)]
    all_mask = (1 << r) - 1
    unions = [{pool: set() for pool in capacity} for _ in range(all_mask + 1)]
    feasible = [False] * (all_mask + 1)
    for mask in range(1, all_mask + 1):
        bit = mask & -mask
        j = bit.bit_length() - 1
        previous = unions[mask ^ bit]
        unions[mask] = {pool: previous[pool] | support[j][pool] for pool in capacity}
        feasible[mask] = all(sum(ports.tensors[t]['size'] for t in unions[mask][pool])
                             <= capacity[pool] for pool in capacity)
    dp = [r + 1] * (all_mask + 1)
    dp[0] = 0
    for mask in range(1, all_mask + 1):
        anchor = mask & -mask
        sub = mask
        while sub:
            if sub & anchor and feasible[sub]:
                dp[mask] = min(dp[mask], 1 + dp[mask ^ sub])
            sub = (sub - 1) & mask
    minimum = None if dp[all_mask] > r else dp[all_mask]
    return {'case': case, 'r': r, 'singleton_support_bytes': singleton,
            'feasible_nonempty_subsets': sum(feasible), 'nonempty_subsets': all_mask,
            'minimum_cores': minimum, 'five_core_possible': minimum is not None and minimum <= 5}


def main():
    start_wall, start_cpu = time.monotonic(), time.process_time()
    signal.signal(signal.SIGALRM, alarm)
    signal.alarm(30)
    actual = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in EXPECTED}
    if actual != EXPECTED:
        raise ValueError('frozen source, config, or input hash changed')
    import configparser
    config = configparser.ConfigParser()
    config.read(ROOT / 'data/raw/a/official/data/config.txt')
    capacity = {pool: config.getint('capacity', pool) for pool in ('L1', 'UB')}
    if capacity != {'L1': 524288, 'UB': 131072}:
        raise ValueError('frozen capacity changed')
    rows = []
    for case in ('005', '086'):
        rows.append(one(case, capacity))
    result = {'source_commit': '65d7355ee0856783ede81328915e8bd43227c842',
              'sha256': actual, 'capacity_bytes': capacity, 'rows': rows,
              'cpu_seconds': time.process_time() - start_cpu,
              'wall_seconds': time.monotonic() - start_wall,
              'official_calls': 0, 'scope': 'static resident-flow necessary condition only'}
    (DIR / 'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(result, ensure_ascii=False))
    signal.alarm(0)


if __name__ == '__main__':
    main()
