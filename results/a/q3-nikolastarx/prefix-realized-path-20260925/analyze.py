"""Offline max-plus audit of one saved official execution; no evaluator imports."""
from collections import Counter, defaultdict
from pathlib import Path
import gzip
import hashlib
import heapq
import json
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = ROOT / 'results/a/q3-nikolastarx'
ARCHIVE = BASE / 'pipeline-prefix-linux-20260925/run-local/evidence.tar.gz'
ARCHIVE_SHA = 'a923a07fc1ad549eecaae227e534d7a7de83ef1647a67a60a70d130c4aef8b05'
RESULT_SHA = 'd4cdf8dbabe22923b9a74329741fb39e74a588e619d9f101db1fd28ecd629da1'
PLAN_SHA = '13914b24c18b59366be17de86a26d227ff85427cb00b184799587777547a6508'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def longest(nodes, edges, durations, finish_floors=None):
    finish_floors = finish_floors or {}
    if set(durations) != set(nodes) or any(x < 0 for x in durations.values()):
        raise ValueError('node durations differ')
    ins = dict.fromkeys(nodes, 0)
    succ = defaultdict(list)
    for (u, v), e in edges.items():
        if u not in ins or v not in ins or e['lag'] < 0:
            raise ValueError('bad edge')
        ins[v] += 1
        succ[u].append((v, e['lag']))
    q = sorted(u for u, n in ins.items() if n == 0)
    heapq.heapify(q)
    start, parent, visited = dict.fromkeys(nodes, 0), {}, 0
    finish = {}
    while q:
        u = heapq.heappop(q)
        visited += 1
        finish[u] = max(start[u] + durations[u], finish_floors.get(u, 0))
        if finish[u] > start[u] + durations[u]:
            parent.pop(u, None)
        for v, lag in succ[u]:
            z = finish[u] + lag
            if z > start[v]:
                start[v], parent[v] = z, u
            ins[v] -= 1
            if ins[v] == 0:
                heapq.heappush(q, v)
    if visited != len(nodes):
        raise ValueError('cycle')
    end = max(nodes, key=lambda u: (finish[u], u))
    total = finish[end]
    path, u = [], end
    while u is not None:
        path.append(u)
        u = parent.get(u)
    return total, start, list(reversed(path))


def main():
    raw = ARCHIVE.read_bytes()
    assert sha(raw) == ARCHIVE_SHA
    with tarfile.open(ARCHIVE, 'r:gz') as tf:
        def member(name):
            m = tf.getmember(name)
            assert m.isfile() and m.size < 10_000_000
            return tf.extractfile(m).read()
        pr = member('probe/prepare/prepared.json.gz')
        rr = member('probe/official-p3.json.gz')
        run = json.loads(member('probe/run.json'))
        prepare_receipt = json.loads(member('probe/prepare/run.json'))
    assert sha(rr) == RESULT_SHA and run['plan_sha256'] == PLAN_SHA
    prepared = json.loads(gzip.decompress(pr))
    result = json.loads(gzip.decompress(rr))
    assert result['data_movement_bytes']['spill_added_copy_bytes'] == 0
    boundpath = BASE / 'pipeline-prefix-bound-20260925/candidate.json'
    boundraw = boundpath.read_bytes()
    bound = json.loads(boundraw)
    tasks = {int(k): v for k, v in prepared['tasks'].items()}
    nodes = {(core['core_id'], o['op_id']): o for core in result['per_core_timeline'] for o in core['ops']}
    edges = {}
    def edge(u, v, lag, kind):
        e = edges.setdefault((u, v), {'lag': lag, 'kinds': set()})
        e['lag'] = max(e['lag'], lag)
        e['kinds'].add(kind)
    base_local = set()
    for c, task in tasks.items():
        # Step2 graph precedes allocation-reuse edges. Reconstruct its ordinary
        # op completion dependencies explicitly from the saved graph only.
        g = prepared['intermediates']['Step2'][c]['graph']
        opids = {x['id'] for x in g['ops']}
        producers, consumers = defaultdict(set), defaultdict(set)
        for e in g['edges']:
            u, v = e['source'], e['target']
            if u in opids and v in opids:
                base_local.add(((c, u), (c, v)))
            elif u in opids:
                producers[v].add(u)
            elif v in opids:
                consumers[u].add(v)
        for tid, ps in producers.items():
            for u in ps:
                for v in consumers[tid]:
                    base_local.add(((c, u), (c, v)))
        memory = {(int(e['source']), int(e['target'])) for e in task['step3']['memory_dependencies']}
        for vv, preds in task['op_preds'].items():
            v = int(vv)
            for uu in preds:
                u = int(uu)
                key = ((c, u), (c, v))
                if key in base_local:
                    edge(*key, 0, 'data')
                if (u, v) in memory:
                    edge(*key, 0, 'memory')
                if key not in base_local and (u, v) not in memory:
                    raise ValueError('unclassified prepared predecessor')
        for order in task['pipe_ops'].values():
            for u, v in zip(order, order[1:]):
                edge((c, u), (c, v), 0, 'fifo')
    for link in prepared['cross_links']:
        edge((link['source_core'], link['source_copy_out_id']),
             (link['target_core'], link['target_copy_in_id']),
             result['cross_core_copy_delay_cycles'], 'cross_release')
    assert all(k in edges for k in base_local)
    copies = {(x['core'], x['op_id']): x for x in bound['copy_nodes']}
    minimum, actual = {}, {}
    for u, trace in nodes.items():
        actual[u] = trace['duration']
        assert trace['end'] - trace['start'] == actual[u]
        if u in copies:
            x = copies[u]
            minimum[u] = x['duration_lower_bound']
            if x['kind'] == 'COPY_IN':
                assert trace['cache_tensor_id'] == x['cache_key']
                assert not (x['sole_copy_in_key_proved_cold'] and trace['cache_hit'])
        else:
            op = tasks[u[0]]['op_by_id'][str(u[1])]
            assert op['pipe'] in {'PIPE_M','PIPE_V'}
            minimum[u] = max(1, op['cycles'])
        assert minimum[u] <= actual[u]
    without_memory = {k:e for k,e in edges.items() if e['kinds'] != {'memory'}}
    base_lb, _, _ = longest(nodes, without_memory, minimum)
    full_lb, _, lbpath = longest(nodes, edges, minimum)
    # Four verified continuously ready cold-read prefixes start at time zero.
    # Their work is official rounded exclusive DDR service, not byte/B fractions.
    prefixes = {}
    external_targets = {(x['target_core'], x['target_copy_in_id']) for x in prepared['cross_links']}
    for check in prepare_receipt['checks']:
        c, order = check['core'], check['prefix']
        if not order:
            continue
        assert all(check['checks'].values())
        assert tasks[c]['pipe_ops']['PIPE_MTE2'][:len(order)] == order
        seen = set()
        for opid in order:
            u = (c, opid)
            assert u not in external_targets and u in copies
            assert copies[u]['kind'] == 'COPY_IN' and copies[u]['sole_copy_in_key_proved_cold']
            assert set(map(int, tasks[c]['op_preds'][str(opid)])).issubset(seen)
            seen.add(opid)
        prefixes[c] = {'ops':order,'work':sum(minimum[c,x] for x in order)}
    floors = {}
    for c, prefix in prefixes.items():
        # Fractional service may complete before integer retirement. Each peer
        # has fewer than len(ops)-1 cycles of internal service gaps.
        lower = prefix['work'] + sum(
            min(x['work'], max(0, prefix['work'] - (len(x['ops']) - 1)))
            for j,x in prefixes.items() if j != c)
        last = (c, prefix['ops'][-1])
        assert nodes[(c,prefix['ops'][0])]['start'] == 0
        assert lower <= nodes[last]['end']
        prefix.update(finish_lower_bound=lower, official_finish=nodes[last]['end'])
        floors[last] = lower
    shared_lb, _, shared_path = longest(nodes, edges, minimum, floors)
    realized, starts, path = longest(nodes, edges, actual)
    mismatches = [{ 'node':u,'reconstructed':starts[u],'official':nodes[u]['start']}
                  for u in nodes if starts[u] != nodes[u]['start']]
    assert base_lb == bound['lower_bound_cycles'], (base_lb, bound['lower_bound_cycles'])
    assert not mismatches, mismatches[:10]
    assert realized == result['makespan']
    assert full_lb <= realized
    contributions, pathrows = Counter(), []
    for i, u in enumerate(path):
        trace = nodes[u]
        prev = path[i-1] if i else None
        arc = edges[(prev,u)] if prev else {'lag':0,'kinds':set()}
        contributions[trace['op']] += actual[u]
        contributions['cross_lag'] += arc['lag']
        contributions['duration_excess_above_minimum'] += actual[u] - minimum[u]
        pathrows.append({'core':u[0],'op_id':u[1],'op':trace['op'],'pipe':trace['pipe'],
                         'start':trace['start'],'end':trace['end'],'duration':actual[u],
                         'minimum_duration':minimum[u], 'incoming_lag':arc['lag'],
                         'incoming_types':sorted(arc['kinds']),
                         'previous':prev, 'cache_hit':trace.get('cache_hit')})
    missing_edges = sum(e['kinds']=={'memory'} for e in edges.values())
    rows = sorted(({'core':u[0],'op_id':u[1],'op':x['op'], 'bytes':copies[u]['bytes'],
                    'duration':actual[u], 'minimum_duration':minimum[u],
                    'excess':actual[u]-minimum[u], 'on_realized_path':u in set(path),
                    'start':x['start'],'end':x['end']}
                    for u,x in nodes.items() if u in copies), key=lambda x:-x['excess'])
    out = {'schema':'q3-saved-realized-path-v1','source_archive_sha256':ARCHIVE_SHA,
           'official_result_sha256':RESULT_SHA,'prepared_sha256':sha(pr),'plan_sha256':PLAN_SHA,
           'analyzer_sha256':sha(Path(__file__).read_bytes()),'prior_bound_sha256':sha(boundraw),
           'source_commit':run['source_commit'],'official_code_sha256':run['official_code_sha256'],
           'op_count':len(nodes),'edge_count':len(edges),'memory_only_edge_count':missing_edges,
           'without_memory_lower_bound':base_lb,'prepared_graph_lower_bound':full_lb,
           'rounded_sharing_model_lower_bound':shared_lb,'cold_prefixes':prefixes,
           'rounded_sharing_bound_scope':'fixed verified prefixes, rational processor-sharing and ceil retirement; mathematical model, not yet a floating-point implementation pruning certificate',
           'shared_prefix_bound_path':shared_path,
           'realized_duration_longest_path':realized,'official_makespan':result['makespan'],
           'all_op_start_times_exact':not mismatches,'critical_path_node_count':len(path),
           'realized_path_contributions':dict(contributions),'critical_path':pathrows,
           'prepared_bound_critical_nodes':lbpath,'copies_by_duration_excess':rows,
           'interpretation':'Minimum-duration path is conditional on this fixed prepared plan. Realized-duration reconstruction is ex-post accounting, not a predictive evaluator or causal replay. Changing any plan or timing may change transfer durations and cache outcomes.',
           'calls':{'Task':0,'Step1':0,'Step2':0,'Step3':0,'E0':0,'solver':0}}
    (HERE/'audit.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in {'critical_path','prepared_bound_critical_nodes','copies_by_duration_excess','shared_prefix_bound_path'}},indent=2))

if __name__ == '__main__':
    main()
