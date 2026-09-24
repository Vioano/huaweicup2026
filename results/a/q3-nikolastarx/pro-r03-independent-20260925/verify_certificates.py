"""Independent check of author JSON witnesses; does not import author code/E0."""
import argparse
from collections import deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def check_schedule(schedule, delta=500):
    operations = schedule['operations']
    ops = {x['op']: x for x in operations}
    assert len(ops) == len(operations)
    words = schedule['core_words']
    flat = [u for word in words for u in word]
    assert len(flat) == len(set(flat)) == len(ops) and set(flat) == set(ops)
    outgoing = {u: {} for u in ops}
    arrivals = {u: 0 for u in ops}
    for u, op in ops.items():
        assert type(op['duration']) is int and op['duration'] > 0
        assert type(op['start']) is int and op['start'] >= 0
        assert op['end'] == op['start'] + op['duration']
        for p in op['predecessors']:
            assert p in ops and p != u
            lag = delta if ops[p]['core'] != op['core'] else 0
            outgoing[p][u] = max(outgoing[p].get(u, 0), lag)
            assert ops[p]['end'] + lag <= op['start']
        for port in op['external_input_ports']:
            lag = delta if port['owner'] is not None and port['owner'] != op['core'] else 0
            arrivals[u] = max(arrivals[u], port['ready'] + lag)
        assert arrivals[u] <= op['start']
    for core, word in enumerate(words):
        previous = {}
        for u in word:
            op = ops[u]
            assert op['core'] == core and op['pipe'] in {'M', 'V'}
            if op['pipe'] in previous:
                p = previous[op['pipe']]
                assert ops[p]['end'] <= op['start']
                outgoing[p][u] = max(outgoing[p].get(u, 0), 0)
            previous[op['pipe']] = u
    indegree = dict.fromkeys(ops, 0)
    for targets in outgoing.values():
        for u in targets:
            indegree[u] += 1
    ready = deque(u for u in ops if not indegree[u])
    finish = {}
    while ready:
        u = ready.popleft()
        finish[u] = arrivals[u] + ops[u]['duration']
        assert finish[u] <= ops[u]['end']
        for v, lag in outgoing[u].items():
            arrivals[v] = max(arrivals[v], finish[u] + lag)
            indegree[v] -= 1
            if not indegree[v]:
                ready.append(v)
    assert len(finish) == len(ops), 'cycle in dependencies plus submitted pipe words'
    witness = max(x['end'] for x in operations)
    assert witness == schedule['makespan']
    return {'operations': len(ops), 'witness_makespan': witness,
            'independent_asap_makespan': max(finish.values()),
            'all_constraints_checked': True}


def check_pair(example):
    a, b = example['baseline'], example['candidate']
    def immutable(s):
        return {x['op']: {k: v for k, v in x.items()
                         if k not in {'core', 'start', 'end'}} for x in s['operations']}
    assert immutable(a) == immutable(b), 'operation, dependency or port mutation'
    old, new = check_schedule(a), check_schedule(b)
    assert new['independent_asap_makespan'] <= old['independent_asap_makespan']
    return {'name': example['name'], 'baseline': old, 'candidate': new}


def must_reject(schedule):
    try:
        check_schedule(schedule)
    except AssertionError:
        return
    raise AssertionError('deliberately invalid witness was accepted')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('certificate', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    raw = args.certificate.read_bytes()
    data = json.loads(raw)
    assert data['official_evaluations'] == 0 and len(data['examples']) == 6
    rows = [check_pair(x) for x in data['examples']]
    bad = deepcopy(data['examples'][0]['candidate'])
    moved = next(x for x in bad['operations'] if x['op'] == 'd2')
    moved['start'] = 4020; moved['end'] = 6020
    must_reject(bad)  # Omits the required 500-cycle incoming release.
    bad = deepcopy(data['examples'][4]['candidate'])
    op = next(x for x in bad['operations'] if x['external_input_ports'])
    op['external_input_ports'][0]['ready'] = 100000
    must_reject(bad)  # Wrong per-input release despite unchanged work/bytes.
    result = {'scope': 'six author synthetic compute+delta witnesses only',
              'source_sha256': hashlib.sha256(raw).hexdigest(),
              'new_official_evaluations': 0, 'author_code_executed': False,
              'negative_checks': 2, 'examples': rows,
              'not_proved': ['official performance', 'general optimality',
                             'capacity/cache correctness', 'production complexity']}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'checked': len(rows), 'negative_checks': 2, 'E0': 0}))


if __name__ == '__main__':
    main()
