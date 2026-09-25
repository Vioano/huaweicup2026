#!/usr/bin/env python3
"""One deterministic R9 fifth-core candidate. Pure static; no official imports.

This covers r=K-1 persistent tracks and an ancestor-closed shared residual.
It does NOT search placements, split/fuse/duplicate ops, call Task/Step/E0,
or predict M2/M3. A failed guard raises and stops, with no alternate candidate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import r9_static_core as r9
from row_recognizer_frozen import _ports, _recognize


def construct(graph: dict, cores: int, capacity: dict, delay: int):
    r9.need(type(cores) is int and cores >= 2, 'requires at least two cores')
    r9.need(set(capacity) == {'L1', 'UB'} and all(type(x) is int and x > 0 for x in capacity.values()), 'bad capacity')
    r9.need(type(delay) is int and delay >= 0, 'bad delay')
    ix = r9.RawIndex.build(graph)
    ports = _ports(ix)
    rows, depth, keys, labels, kv, qsucc = r9.recognize_layers(ix, ports, _recognize)
    tracks, private, parts, phase, up, down, anchors, sigs = r9.decompose(ix, labels, kv)
    r9.need(len(tracks) == cores-1, 'requires exactly K-1 persistent tracks')
    r9.need(bool(parts), 'no shared residual to offload')
    r9.need(all(ports.outputs[u] for u in ix.ops), 'every compute op needs an output')
    extra = cores-1
    owner = {u: i for u, i in private.items()}
    for part in parts:
        owner.update({u: extra for u in part})
    r9.need(set(owner) == set(ix.ops), 'incomplete/overlapping ownership')

    def key(part):
        consumers = {v for u in part for v in ix.succ[u] if v in private}
        return (not bool(consumers), min((phase[v] for v in consumers), default=10**9), min(part))

    ordered = sorted(parts, key=key)
    microphase = {u: phase[u] for u in private}
    for j, part in enumerate(ordered):
        for u in part:
            microphase[u] = j-len(ordered)
    # Microphase is construction-only metadata, NOT a submitted completion barrier.
    words, tau = r9.priority_words(ix, microphase, owner, cores, delay)
    memory, intervals = r9.interval_certificate(ix, ports, owner, words, capacity)
    r9.need(memory['step2_no_spill_certificate'], 'one candidate exceeded bucket-frontier capacity; stop')
    mv = r9.path_stats(ix, owner, words, tau, delay)
    envelope = r9.path_stats(ix, owner, words, tau, delay, True)
    r9.need(envelope['max_remote_edges'] <= 2+max(depth.values()), 'L+1 path-count guard failed')
    traffic, links = r9.traffic_counts(ix, ports, owner, kv)
    mapping = {str(u): j for j, u in enumerate(ix.order)}
    plan = {'node_to_subgraph': mapping,
            'core_schedules': [[mapping[str(u)] for u in word] for word in words]}
    metadata = {
        'status': 'STATIC_ONLY_NOT_OFFICIALLY_EVALUATED', 'official_calls': 0,
        'rule': 'component_contiguous_extra_core', 'M3': None, 'M2': None, 'G': None,
        'tracks': tracks, 'private_ops': len(private), 'shared_components': len(parts),
        'shared_ops': sum(map(len,parts)),
        'ordered_components': [{'min_op_id':min(part), 'nodes':sorted(part),
            'kind':'terminal' if key(part)[0] else 'feeder'} for part in ordered],
        'core_lengths': list(map(len,words)),
        'core_work_M_V': [[sum(ix.duration(u) for u in w if ix.ops[u]['pipe']==p) for p in r9.PIPES] for w in words],
        'memory': memory, 'compute_MV_FIFO': mv, 'whole_word_envelope': envelope,
        'traffic_prediction': traffic,
    }
    evidence = {'global_tau':tau, 'core_compute_words':words, 'owner':owner,
                'intervals':intervals, 'source_rule_cross_links':links}
    return plan, metadata, evidence


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--graph', type=Path, required=True)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--cores', type=int, default=5)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    r9.need(not args.out.exists(), 'refuse to overwrite an output directory')
    cfg = {}; section = None
    for line in args.config.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('['): section=line[1:-1];cfg[section]={}
        else:
            k,v=line.split();cfg[section][k]=int(v)
    raw = args.graph.read_bytes()
    plan, meta, evidence = construct(json.loads(raw), args.cores, cfg['capacity'],
                                     cfg['multicore_scene_b']['cross_core_copy_delay_cycles'])
    encode=lambda obj:(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
    data=encode(plan)
    meta.update(graph_sha256=hashlib.sha256(raw).hexdigest(),
                config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),
                plan_sha256=hashlib.sha256(data).hexdigest())
    args.out.mkdir(parents=True)
    (args.out/'plan.json').write_bytes(data)
    (args.out/'metadata.json').write_bytes(encode(meta))
    (args.out/'evidence.json').write_bytes(encode(evidence))
    print(json.dumps({'plan_sha256':meta['plan_sha256'],'official_calls':0,
                      'memory':meta['memory']['bucket_frontier_peaks']},ensure_ascii=False))

if __name__=='__main__':main()
