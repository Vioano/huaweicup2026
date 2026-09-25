#!/usr/bin/env python3
"""R9: persistent layered query affinity, raw-DAG-only constructor.

No official Task/Step/evaluator is invoked. The frozen row recognizer is reused
from the input packet. All outputs are singleton submissions and STATIC proofs,
not official scores. Unsupported structures raise GuardError; no fallback or
unbounded parameter sweep is hidden here.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import heapq
import json
from pathlib import Path
import sys
import time
from typing import Iterable

PIPES = ('PIPE_M', 'PIPE_V')
COPY = {'COPY_IN', 'COPY_OUT'}
RECOGNIZER_SHA = 'a4076188bda3037cdaa22686bf85d20051a3d8020e02d78d46db36adc5c10bb9'
FORBIDDEN = {'_build_scene_b_tasks', 'step1_schedule', 'step1_from_adj',
             'step2_spill_insertion', 'prepare_step3_execution',
             'step3_simulation', 'evaluate_problem_3', 'evaluate_scene_b',
             'evaluate_problem_2', 'evaluate_multicore', 'derive_multicore_plan'}

class GuardError(ValueError):
    pass

def need(ok, message):
    if not ok:
        raise GuardError(message)

def bit_union(values: Iterable[int]) -> int:
    result = 0
    for value in values:
        result |= value
    return result

def bit_members(mask: int):
    while mask:
        b = mask & -mask
        yield b.bit_length() - 1
        mask -= b

def topo(nodes, succ):
    degree = {u: 0 for u in nodes}
    for u in nodes:
        for v in succ[u]:
            degree[v] += 1
    ready = [u for u in nodes if degree[u] == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        u = heapq.heappop(ready)
        result.append(u)
        for v in sorted(succ[u]):
            degree[v] -= 1
            if degree[v] == 0:
                heapq.heappush(ready, v)
    need(len(result) == len(nodes), 'input/quotient cycle')
    return result

@dataclass
class RawIndex:
    graph: dict
    ops: dict
    pred: dict
    succ: dict
    order: list

    def duration(self, u):
        return self.ops[u]['cycles']

    @classmethod
    def build(cls, graph):
        all_ops = {o['id']: o for o in graph['ops']}
        tensors = {t['id']: t for t in graph['tensors']}
        need(len(all_ops) == len(graph['ops']) and len(tensors) == len(graph['tensors'])
             and not (all_ops.keys() & tensors.keys()), 'IDs must be unique/disjoint')
        need(all(type(u) is int and u >= 0 for u in all_ops.keys() | tensors.keys()), 'invalid ID')
        edge_pairs = [(e['source'], e['target']) for e in graph['edges']]
        need(len(set(edge_pairs)) == len(edge_pairs), 'duplicate original edges')
        producers, inputs = {}, defaultdict(set)
        for e in graph['edges']:
            u, v = e['source'], e['target']
            if u in all_ops and v in tensors:
                need(v not in producers or producers[v] == u, 'multiple tensor producers')
                producers[v] = u
            elif u in tensors and v in all_ops:
                inputs[v].add(u)
            else:
                raise GuardError('only original tensor-mediated edges are supported')
        ap = {u: {producers[t] for t in inputs[u] if t in producers} for u in all_ops}
        ass = {u: set() for u in all_ops}
        for v in ap:
            for u in ap[v]:
                ass[u].add(v)
        ao = topo(all_ops, ass)
        ops = {u: o for u, o in all_ops.items() if o['op'] not in COPY}
        need(bool(ops), 'empty compute graph')
        need(all(o['pipe'] in PIPES and type(o['cycles']) is int and o['cycles'] > 0
                 for o in ops.values()), 'positive M/V compute durations required')
        # Independent nearest-compute contraction, not an official routine.
        nearest, contracted = {}, {}
        for u in ao:
            previous = set().union(*(nearest[p] for p in ap[u]))
            if u in ops:
                contracted[u] = previous
                nearest[u] = {u}
            else:
                nearest[u] = previous
        pred = {u: ap[u] & ops.keys() for u in ops}
        need(pred == contracted, 'COPY contraction differs from direct tensor dependencies')
        succ = {u: set() for u in ops}
        for v in ops:
            for u in pred[v]:
                succ[u].add(v)
        return cls(graph, ops, pred, succ, topo(ops, succ))

def recognize_layers(index, ports, recognize):
    rows = recognize(index, ports)
    node_row = {}
    for i, row in enumerate(rows):
        for u in row['nodes']:
            need(u not in node_row, 'row overlap')
            node_row[u] = i
    last = {}
    for u in index.order:
        last[u] = (1 << node_row[u]) if u in node_row else bit_union(last[p] for p in index.pred[u])
    qsucc = {i: set() for i in range(len(rows))}
    for i, row in enumerate(rows):
        inside = set(row['nodes'])
        mask = bit_union(last[p] for u in inside for p in index.pred[u] - inside)
        need(not (mask >> i & 1), 'row reentry')
        for j in bit_members(mask):
            qsucc[j].add(i)
    depth = {i: 0 for i in qsucc}
    for i in topo(qsucc, qsucc):
        for j in qsucc[i]:
            depth[j] = max(depth[j], depth[i] + 1)
    qu, ku, vu = defaultdict(set), defaultdict(set), defaultdict(set)
    for row in rows:
        for t in ports.inputs[row['q']]:
            qu[t].add(row['q'])
        for u in row['k']:
            for t in ports.inputs[u]: ku[t].add(u)
        for u in row['v']:
            for t in ports.inputs[u]: vu[t].add(u)
    keys = []
    for row in rows:
        need(all(index.ops[u]['op'] == 'MATMUL' for u in (row['q'], *row['k'], *row['v'])),
             'projection is not MATMUL')
        candidates = [t for t in ports.inputs[row['q']] if ku[t] and vu[t]]
        need(bool(candidates), 'missing Q/K/V raw input key')
        least = min(len(qu[t]) for t in candidates)
        best = [t for t in candidates if len(qu[t]) == least]
        need(len(best) == 1, 'ambiguous raw input key')
        keys.append(best[0])
    key_depth = {}
    for i, key in enumerate(keys):
        need(key not in key_depth or key_depth[key] == depth[i], 'key reused across depths')
        key_depth[key] = depth[i]
    labels = {}
    for i, row in enumerate(rows):
        for u in row['nodes']:
            labels[u] = ('A', depth[i], keys[i])
    for row in rows:
        for u in (row['q'], *row['k'], *row['v']):
            found = ports.inputs[u] & key_depth.keys()
            need(len(found) == 1, 'projection input key is not unique')
            key = next(iter(found)); label = ('P', key_depth[key], key)
            need(u not in labels or labels[u] == label, 'projection/row collision')
            labels[u] = label
    kv = {(p, v) for row in rows for p in (*row['k'], *row['v'])
          for v in row['nodes'] if v in index.succ[p]}
    return rows, depth, keys, labels, kv, qsucc

def decompose(index, labels, kv):
    anchors = sorted(set(labels.values()))
    bit = {a: 1 << i for i, a in enumerate(anchors)}
    up, down = {}, {}
    for u in index.order:
        up[u] = bit[labels[u]] if u in labels else bit_union(up[p] for p in index.pred[u])
    for u in reversed(index.order):
        down[u] = bit[labels[u]] if u in labels else bit_union(down[v] for v in index.succ[u])
    def symbols(mask):
        return {(anchors[i][1], anchors[i][2]) for i in bit_members(mask)}
    syms = sorted({a[1:] for a in anchors}); parent = {s: s for s in syms}
    def find(s):
        while parent[s] != s:
            parent[s] = parent[parent[s]]; s = parent[s]
        return s
    for u in index.order:
        if u not in labels and up[u]:
            ss = sorted(symbols(up[u] | down[u]))
            for s in ss[1:]: parent[find(s)] = find(ss[0])
    # Direct anchor handoffs are zero-interior bridges. Only recognized K/V
    # broadcasts are excluded; no original edge is removed from scheduling.
    for u in index.order:
        for v in index.succ[u]:
            if u in labels and v in labels and (u, v) not in kv:
                parent[find(labels[u][1:])] = find(labels[v][1:])
    components = defaultdict(list)
    for s in syms: components[find(s)].append(s)
    tracks = sorted((sorted(ss) for ss in components.values()), key=lambda ss: ss[0])
    for track in tracks:
        need(len({l for l, _ in track}) == len(track),
             'genuine cross-stream bridge/join: two keys of one depth in one lineage')
    track_of = {s: i for i, track in enumerate(tracks) for s in track}
    fixed = {u: track_of[a[1:]] for u, a in labels.items()}
    for u in index.order:
        if u not in labels and up[u]:
            ts = {track_of[s] for s in symbols(up[u] | down[u])}
            need(len(ts) == 1, 'dynamic bridge cannot be assigned to one track')
            fixed[u] = next(iter(ts))
    dest = {}
    for u in reversed(index.order):
        dest[u] = {fixed[u]} if u in fixed else set().union(*(dest[v] for v in index.succ[u]))
    private = dict(fixed); shared = set()
    for u in index.order:
        if u not in fixed:
            if len(dest[u]) == 1: private[u] = next(iter(dest[u]))
            else: shared.add(u)
    need(set(private) | shared == set(index.ops) and not (private.keys() & shared), 'incomplete ownership')
    need(all(p in shared for u in shared for p in index.pred[u]),
         'shared auxiliary set must be ancestor-closed')
    parts = []; remaining = set(shared)
    while remaining:
        part, todo = set(), [min(remaining)]
        while todo:
            u = todo.pop()
            if u not in remaining: continue
            remaining.remove(u); part.add(u)
            todo.extend((index.pred[u] | index.succ[u]) & remaining)
        parts.append(part)
    phase = {}
    for u in index.order:
        if u in shared: phase[u] = 0
        elif u in labels:
            st, l, _ = labels[u]; phase[u] = 2 + 3*l + int(st == 'A')
        elif up[u]: phase[u] = 4 + 3*max(l for l, _ in symbols(up[u]))
        else: phase[u] = 1
    for u in index.order:
        for v in index.succ[u]:
            need(phase[u] <= phase[v], f'backward phase edge {u}->{v}')
            if u in private and v in private and private[u] != private[v]:
                need((u, v) in kv and u in labels and v in labels
                     and labels[u][0] == 'P' and labels[v][0] == 'A'
                     and labels[u][1] == labels[v][1], f'unrecognized cross-track edge {u}->{v}')
    signatures = defaultdict(list)
    for u in index.order:
        if u not in labels: signatures[(up[u], down[u])].append(u)
    return tracks, private, parts, phase, up, down, anchors, signatures

def partition_tracks(index, private, r, cores):
    need(1 <= cores <= r <= 10, 'bounded subset DP requires 1 <= cores <= tracks <= 10')
    work = [[0, 0] for _ in range(r)]
    for u, i in private.items(): work[i][PIPES.index(index.ops[u]['pipe'])] += index.duration(u)
    totals = [(0, 0)] * (1 << r)
    for mask in range(1, 1 << r):
        b = mask & -mask; i = b.bit_length()-1
        totals[mask] = tuple(totals[mask-b][p] + work[i][p] for p in range(2))
    transitions = 0
    @lru_cache(None)
    def bottleneck(k, mask):
        nonlocal transitions
        if k == 0: return 0 if mask == 0 else None
        if mask.bit_count() < k: return None
        least = mask & -mask; sub = mask; best = None
        while sub:
            if sub & least and (mask ^ sub).bit_count() >= k-1:
                transitions += 1
                tail = bottleneck(k-1, mask ^ sub)
                if tail is not None:
                    trial = max(max(totals[sub]), tail)
                    if best is None or trial < best: best = trial
            sub = (sub-1) & mask
        return best
    optimum = bottleneck(cores, (1 << r)-1)
    need(optimum is not None, 'no subset partition')
    # A max objective can mask a suffix bottleneck. Do NOT store just a
    # lexicographic (max, sumsq) suffix label. Fix the optimum first, then
    # minimize the additive tie-break under that threshold.
    tie_transitions = 0
    @lru_cache(None)
    def tie(k, mask):
        nonlocal tie_transitions
        if k == 0: return (0, ()) if mask == 0 else None
        if mask.bit_count() < k: return None
        least=mask & -mask; sub=mask; best=None
        while sub:
            if sub & least and max(totals[sub]) <= optimum and (mask ^ sub).bit_count() >= k-1:
                tie_transitions += 1
                tail=tie(k-1, mask ^ sub)
                if tail is not None:
                    w=totals[sub]
                    trial=(w[0]**2+w[1]**2+tail[0],(sub,)+tail[1])
                    if best is None or trial < best: best=trial
            sub=(sub-1)&mask
        return best
    best=tie(cores,(1<<r)-1)
    need(best is not None, 'tie pass lost the optimal bottleneck')
    groups=[list(bit_members(mask)) for mask in best[1]]
    return groups, {'track_work_M_V':work,'bottleneck_private_pipe_work':optimum,
                    'tie_break_sum_squared_pipe_work':best[0],
                    'dp_states':bottleneck.cache_info().currsize,
                    'dp_transitions':transitions,
                    'tie_dp_states':tie.cache_info().currsize,
                    'tie_dp_transitions':tie_transitions,
                    'objective':'exact two-pass lexicographic load proxy; NOT official Makespan optimum'}

def assign_shared(index, ports, private, parts, groups):
    track_core = {i: c for c, group in enumerate(groups) for i in group}
    owner = {u: track_core[i] for u, i in private.items()}
    loads = [[0, 0] for _ in groups]
    for u, c in owner.items(): loads[c][PIPES.index(index.ops[u]['pipe'])] += index.duration(u)
    for part in sorted(parts, key=min):
        work = [sum(index.duration(u) for u in part if index.ops[u]['pipe']==p) for p in PIPES]
        trials = []
        for c in range(len(groups)):
            out = 0
            for u in part:
                for t in ports.outputs[u]:
                    dest = {owner[v] for v in ports.consumers[t] if v in owner}
                    out += ports.tensors[t]['size'] * len(dest-{c})
            mx = max(loads[k][j]+(work[j] if k==c else 0)
                     for k in range(len(groups)) for j in range(2))
            trials.append((out, mx, c))
        _, _, c = min(trials)
        for u in part: owner[u] = c
        for j in range(2): loads[c][j] += work[j]
    return owner, loads

def priority_words(index, phase, owner, cores, delay):
    bottom = {}
    for u in reversed(index.order):
        bottom[u] = index.duration(u)+max((bottom[v] for v in index.succ[u]), default=0)
    free = {(c,p):0 for c in range(cores) for p in PIPES}
    # Start-order clock reflects the fact every original op has an on-chip output.
    # It is still not a COPY/DDR/cache/Step3 timing model.
    alloc_clock = [0]*cores; finish = {}; words = [[] for _ in range(cores)]; tau = []
    for ph in sorted(set(phase.values())):
        nodes = {u for u in index.ops if phase[u]==ph}
        degree = {u:len(index.pred[u]&nodes) for u in nodes}
        ready = {u for u in nodes if degree[u]==0}
        while ready:
            trials=[]
            for u in ready:
                need(index.pred[u] <= finish.keys(), 'global phase order is not topological')
                c=owner[u]; p=index.ops[u]['pipe']
                release=max((finish[v]+delay*int(owner[v]!=c) for v in index.pred[u]),default=0)
                start=max(release,free[c,p],alloc_clock[c])
                trials.append((start,-bottom[u],u))
            start,_,u=min(trials); ready.remove(u); c=owner[u]; p=index.ops[u]['pipe']
            finish[u]=start+index.duration(u); free[c,p]=finish[u]; alloc_clock[c]=start
            words[c].append(u); tau.append(u)
            for v in index.succ[u]&nodes:
                degree[v]-=1
                if degree[v]==0:ready.add(v)
        need(not any(degree.values()), 'phase cycle')
    need(len(tau)==len(index.ops) and len(set(tau))==len(tau), 'word coverage failure')
    return words,tau

def interval_certificate(index, ports, owner, words, capacity):
    need(set(capacity)=={'L1','UB'}, 'capacity pools must be L1 and UB')
    need(all(ports.outputs[u] for u in index.ops), 'each compute op must produce an on-chip output')
    position={u:i for word in words for i,u in enumerate(word)}
    diff=[{p:[0]*(len(word)+1) for p in capacity} for word in words]
    unions=[{p:0 for p in capacity} for _ in words]; intervals=[]
    for tid,t in sorted(ports.tensors.items()):
        pos='UB' if t['pos']=='DDR' else t['pos']
        need(pos in capacity and type(t['size']) is int and t['size']>=0, 'invalid tensor pool/size')
        touches=defaultdict(list)
        source=ports.producer.get(tid)
        if source in owner:touches[owner[source]].append(position[source])
        for v in ports.consumers[tid]:
            if v in owner:touches[owner[v]].append(position[v])
        for c,points in touches.items():
            first,last=min(points),max(points)
            need(source not in owner or owner[source]!=c or first==position[source], 'local tensor used before producer')
            diff[c][pos][first]+=t['size'];diff[c][pos][last+1]-=t['size'];unions[c][pos]+=t['size']
            intervals.append({'core':c,'tid':tid,'pool':pos,'bytes':t['size'],'first_bucket':first,'last_bucket':last})
    peaks=[]
    for c,word in enumerate(words):
        row={}
        for pos in capacity:
            val=0;maximum=0;arg=0
            for i,delta in enumerate(diff[c][pos][:-1]):
                val+=delta
                if val>maximum:maximum,arg=val,i
            row[pos]={'bytes':maximum,'bucket':arg,'op':word[arg] if word else None}
        peaks.append(row)
    passed=all(row[p]['bytes']<=capacity[p] for row in peaks for p in capacity)
    return {'bucket_frontier_peaks':peaks,'ever_touched_union_bytes':unions,
            'step2_no_spill_certificate':passed,
            'union_guard_passes':all(row[p]<=capacity[p] for row in unions for p in capacity),
            'runtime_memory_peak':None,'prepared_memory_edges':None,
            'note':'Frontier equals hypothetical no-spill Step2 peak under singleton/source guards. It is NOT a runtime Step3 peak or a no-memory-edge certificate.'},intervals

def path_stats(index,owner,words,tau,delay,full_core=False):
    edges={u:{v:int(owner[u]!=owner[v]) for v in index.succ[u]} for u in index.ops}
    for word in words:
        tails={}
        for u in word:
            p='ALL' if full_core else index.ops[u]['pipe']
            if p in tails:edges[tails[p]][u]=0
            tails[p]=u
    zero={u:0 for u in index.ops};weighted=dict(zero);count=dict(zero);parent={}
    rank={u:i for i,u in enumerate(tau)}
    for u in tau:
        for v,b in sorted(edges[u].items()):
            need(rank[u]<rank[v], 'augmented priority graph is cyclic')
            zero[v]=max(zero[v],zero[u]+index.duration(u))
            weighted[v]=max(weighted[v],weighted[u]+index.duration(u)+delay*b)
            if count[u]+b>count[v]:count[v]=count[u]+b;parent[v]=(u,b)
    end=max(tau,key=lambda u:(count[u],-u));path=[];v=end
    while v in parent:
        u,b=parent[v];path.append([u,v,b]);v=u
    path.reverse()
    return {'L0':max(zero[u]+index.duration(u) for u in tau),
            'Ldelta':max(weighted[u]+index.duration(u) for u in tau),
            'max_remote_edges':max(count.values()),'remote_path_witness':path,
            'interpretation':('Conservative envelope for complete-path remote COUNT, including possible COPY FIFO and memory edges; L values are NOT official bounds.' if full_core else
                              'Original compute plus M/V FIFO fixed-plan lower bound; omits COPY service, bandwidth, cache and memory edges.')}

def traffic_counts(index,ports,owner,kv):
    originals={o['id']:o for o in index.graph['ops']};total=0;cross=0;links=[];cache_keys=set();raw=0
    for t,rec in ports.tensors.items():
        src=ports.producer.get(t);sc=owner.get(src)
        dest={owner[v] for v in ports.consumers[t] if v in owner}
        cout=any(originals[v]['op']=='COPY_OUT' for v in ports.consumers[t])
        n=0
        if sc is None and dest:n+=len(dest);cache_keys.add(t)
        if sc is not None and (cout or not dest):n+=1
        if sc is not None:
            for dc in sorted(dest-{sc}):
                n+=2;cross+=rec['size'];cache_keys.add(t)
                vs=sorted(v for v in ports.consumers[t] if v in owner and owner[v]==dc)
                links.append({'tid':t,'source_op':src,'source_core':sc,'target_core':dc,
                              'bytes':rec['size'],'consumer_ops':vs,
                              'all_edges_recognized_kv':all((src,v) in kv for v in vs)})
        total+=n*rec['size']
        if src in originals and originals[src]['op']=='COPY_IN':raw+=rec['size']
        raw+=sum(rec['size'] for v in ports.consumers[t] if originals[v]['op']=='COPY_OUT')
    return {'expected_task_copy_bytes_without_spill':total,'original_copy_bytes':raw,
            'expected_added_copy_bytes_without_spill':total-raw,
            'cross_core_payload_bytes':cross,'cross_core_links':len(links),
            'cache_key_union_bytes_without_spill':sum(ports.tensors[t]['size'] for t in cache_keys),
            'note':'Source-rule counts only; no measured traffic, hit rate or cycle value.'},links

def encode(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()

def construct(graph,cores,capacity,delay,recognize,ports_builder):
    index=RawIndex.build(graph); ports=ports_builder(index)
    rows,depth,keys,labels,kv,qsucc=recognize_layers(index,ports,recognize)
    tracks,private,parts,phase,up,down,anchors,sigs=decompose(index,labels,kv)
    groups,dp=partition_tracks(index,private,len(tracks),cores)
    owner,loads=assign_shared(index,ports,private,parts,groups)
    words,tau=priority_words(index,phase,owner,cores,delay)
    memory,intervals=interval_certificate(index,ports,owner,words,capacity)
    need(memory['step2_no_spill_certificate'],'selected direct construction exceeds no-spill frontier guard; no search/retry')
    mv=path_stats(index,owner,words,tau,delay)
    envelope=path_stats(index,owner,words,tau,delay,True)
    layers=1+max(depth.values())
    need(envelope['max_remote_edges']<=layers+1,'whole-path L+1 crossing proof failed')
    traffic,links=traffic_counts(index,ports,owner,kv)
    mapping={str(u):i for i,u in enumerate(index.order)}
    plan={'node_to_subgraph':mapping,'core_schedules':[[mapping[str(u)] for u in w] for w in words]}
    metadata={'status':'STATIC_CONSTRUCTED_NOT_OFFICIALLY_EVALUATED','strategy':'layered_persistent_affinity_r9',
              'original_compute_ops':len(index.ops),'rows':len(rows),'layers':layers,'tracks':tracks,
              'selected_groups':groups,'phase_counts':dict(sorted(Counter(phase.values()).items())),
              'recognized_row_ops':sum(a[0]=='A' for a in labels.values()),
              'projection_ops':sum(a[0]=='P' for a in labels.values()),
              'non_anchor_bridge_and_auxiliary_ops':len(index.ops)-len(labels),
              'stopped_signature_classes':len(sigs),'private_track_ops':len(private),
              'shared_components':[sorted(p) for p in parts], 'core_pipe_work_M_V':loads,
              'subset_dp':dp,'memory':memory,'compute_mv_fifo':mv,'whole_path_envelope':envelope,
              'traffic_prediction':traffic,'M3':None,'M2':None,'G':None,
              'capacity':capacity,'delay':delay,'official_calls':0,
              'first_row_quotient_depth_pair_counts':dict(Counter(f'{depth[u]}->{depth[v]}' for u in qsucc for v in qsucc[u]))}
    ownership=[{'op':u,'core':owner[u],'track':private.get(u),'phase':phase[u],
                'anchor':labels.get(u),'first_upstream_anchors':[anchors[i] for i in bit_members(up[u])],
                'first_downstream_anchors':[anchors[i] for i in bit_members(down[u])]}
               for u in index.order]
    return plan,metadata,{'ownership':ownership,'global_topological_priority':tau,'intervals':intervals,'cross_links':links}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True,help='extracted frozen packet/repository root')
    parser.add_argument('--graph',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--cores',type=int,default=5)
    args=parser.parse_args();root=args.root.resolve();start=time.perf_counter()
    need(hashlib.sha256((root/'src/q3/attention_rows.py').read_bytes()).hexdigest()==RECOGNIZER_SHA,
         'frozen recognizer SHA differs')
    # Verify every packet payload before importing any helper. This is identity,
    # not a claim of having semantically reviewed all 100 files.
    manifest_path=root/'MANIFEST.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        for rec in manifest['files']:
            b=(root/rec['path']).read_bytes()
            need(len(b)==rec['bytes'] and hashlib.sha256(b).hexdigest()==rec['sha256'],
                 f'packet hash mismatch: {rec["path"]}')
    calls=Counter()
    def profile(frame,event,arg):
        if event=='call':
            name=frame.f_code.co_name;filename=frame.f_code.co_filename.replace('\\','/')
            if name in FORBIDDEN and '/data/raw/a/official/code/' in filename:
                calls[name]+=1
                raise RuntimeError(f'FORBIDDEN official invocation: {name}')
    need(sys.getprofile() is None,'unexpected profiler installed')
    sys.setprofile(profile)
    try:
        sys.path.insert(0,str(root))
        from src.q3.attention_rows import _ports,_recognize
        # Minimal config parser, never calls an official config/evaluation routine.
        cfg={};section=None
        for line in (root/'data/raw/a/official/data/config.txt').read_text().splitlines():
            line=line.strip()
            if not line or line.startswith('#'):continue
            if line.startswith('['):section=line[1:-1];cfg[section]={}
            else:
                k,v=line.split();cfg[section][k]=int(v)
        gb=args.graph.read_bytes();graph=json.loads(gb)
        plan,metadata,evidence=construct(graph,args.cores,cfg['capacity'],cfg['multicore_scene_b']['cross_core_copy_delay_cycles'],_recognize,_ports)
    finally:
        sys.setprofile(None)
    need(not args.out.exists(),'output directory exists; no overwrite')
    args.out.mkdir(parents=True)
    planbytes=encode(plan)
    metadata.update(graph_sha256=hashlib.sha256(gb).hexdigest(),
                    config_sha256=hashlib.sha256((root/'data/raw/a/official/data/config.txt').read_bytes()).hexdigest(),
                    constructor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    plan_sha256=hashlib.sha256(planbytes).hexdigest(),
                    forbidden_official_calls=dict(calls),
                    elapsed_static_seconds=time.perf_counter()-start,
                    timing_scope='local profiled static construction including input/hash work; NOT cold solver efficiency acceptance')
    (args.out/'plan.json').write_bytes(planbytes)
    (args.out/'metadata.json').write_bytes(encode(metadata))
    (args.out/'evidence.json').write_bytes(encode(evidence))
    print(json.dumps({'out':str(args.out),'groups':metadata['selected_groups'],
                      'Ldelta_MV':metadata['compute_mv_fifo']['Ldelta'],
                      'D_envelope':metadata['whole_path_envelope']['max_remote_edges'],
                      'frontier':metadata['memory']['bucket_frontier_peaks'],
                      'union':metadata['memory']['ever_touched_union_bytes'],
                      'traffic':metadata['traffic_prediction'],
                      'official_calls':0},ensure_ascii=False))

if __name__=='__main__': main()
