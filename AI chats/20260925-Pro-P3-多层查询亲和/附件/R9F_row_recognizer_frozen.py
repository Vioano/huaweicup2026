"""Unchanged pure _ports/_recognize extraction from the fixed row recognizer.
No official imports. See SOURCE_AUDIT.md for original blob identity.
"""
from collections import defaultdict
from dataclasses import dataclass
class UnsupportedStructure(ValueError):
    pass

class _NotRow(Exception):
    """An expected motif mismatch, never an internal programming error."""


def _match(condition):
    if not condition:
        raise _NotRow


@dataclass(frozen=True)
class _Ports:
    tensors: dict
    producer: dict
    consumers: dict
    inputs: dict
    outputs: dict


def _ports(index):
    """Reject raw edges whose communication the timing model cannot represent."""
    graph = index.graph
    all_ops = {o["id"]: o for o in graph["ops"]}
    tensors = {t["id"]: t for t in graph["tensors"]}
    if (len(all_ops) != len(graph["ops"]) or len(tensors) != len(graph["tensors"])
            or set(all_ops) & set(tensors)):
        raise UnsupportedStructure("requires unique, disjoint operation/tensor IDs")
    eligible = {u for u, op in all_ops.items()
                if op["op"] not in {"COPY_IN", "COPY_OUT"}}
    if eligible != set(index.ops):
        raise UnsupportedStructure("Index does not match the raw graph's compute operations")
    if not eligible or any(op["pipe"] not in {"PIPE_M", "PIPE_V"}
                           or type(op["cycles"]) is not int or op["cycles"] < 1
                           for op in index.ops.values()):
        raise UnsupportedStructure("requires positive integer M/V compute durations")
    producer = {}
    consumers = defaultdict(set)
    inputs = defaultdict(set)
    outputs = defaultdict(set)
    for edge in graph["edges"]:
        u, v = edge["source"], edge["target"]
        if u in tensors and v in all_ops:
            consumers[u].add(v)
            inputs[v].add(u)
        elif u in all_ops and v in tensors:
            if v in producer and producer[v] != u:
                raise UnsupportedStructure("tensor has multiple original producers")
            producer[v] = u
            outputs[u].add(v)
        else:
            raise UnsupportedStructure("requires tensor-mediated edges; direct edges unsupported")
    pred = {u: set() for u in index.ops}
    succ = {u: set() for u in index.ops}
    for v in index.ops:
        for t in inputs[v]:
            u = producer.get(t)
            if u in index.ops:
                pred[v].add(u)
                succ[u].add(v)
    if any(pred[u] != index.pred[u] or succ[u] != index.succ[u] for u in index.ops):
        raise UnsupportedStructure("COPY-contracted dependencies differ from direct tensor dependencies")
    return _Ports(tensors, producer, consumers, inputs, outputs)


def _recognize(index, ports):
    """Find exact multi-entry, single-exit row motifs by original dependencies."""
    kind = lambda u: index.ops[u]["op"]

    def add_tree(root, leaf_kind):
        leaves, inside, stack = set(), set(), [root]
        while stack:
            u = stack.pop()
            if u in inside or u in leaves:
                continue
            if kind(u) == leaf_kind:
                leaves.add(u)
            else:
                _match(kind(u) == "ADD" and len(index.pred[u]) == 2)
                inside.add(u)
                stack.extend(index.pred[u])
        _match(len(leaves) >= 2 and len(inside) == len(leaves) - 1)
        return leaves, inside

    def reverse_until(root, stops):
        inside, found, stack = set(), set(), [root]
        while stack:
            u = stack.pop()
            if u in stops:
                found.add(u)
            elif u not in inside:
                inside.add(u)
                stack.extend(index.pred[u])
        return inside, found

    def try_roles(root, denominator, numerator):
        reds, dadds = add_tree(denominator, "REDUCE")
        mults, nadds = add_tree(numerator, "MATMUL")
        _match(len(reds) == len(mults))
        exp_to_red = {}
        for r in sorted(reds):
            _match(len(index.pred[r]) == 1)
            e = next(iter(index.pred[r]))
            _match(kind(e) == "EXP" and e not in exp_to_red)
            exp_to_red[e] = r
        exps = set(exp_to_red)
        exp_to_mult, vs = {}, set()
        for m in sorted(mults):
            ep = index.pred[m] & exps
            _match(len(ep) == 1 and len(index.pred[m]) == 2)
            e = next(iter(ep))
            v = next(iter(index.pred[m] - ep))
            _match(e not in exp_to_mult and kind(v) == "MATMUL")
            exp_to_mult[e] = m
            vs.add(v)
        _match(set(exp_to_mult) == exps and len(vs) == len(exps))
        shifts, scores, max_roots = set(), set(), set()
        for e in sorted(exps):
            _match(len(index.pred[e]) == 1)
            s = next(iter(index.pred[e]))
            _match(kind(s) == "SUB" and len(index.pred[s]) == 2)
            ds = {p for p in index.pred[s] if kind(p) == "DIV"}
            ms = {p for p in index.pred[s] if kind(p) == "ADD"}
            _match(len(ds) == len(ms) == 1)
            shifts.add(s)
            scores.update(ds)
            max_roots.update(ms)
        _match(len(scores) == len(exps) and len(max_roots) == 1)
        score_mults = set()
        for d in sorted(scores):
            _match(len(index.pred[d]) == 1)
            m = next(iter(index.pred[d]))
            _match(kind(m) == "MATMUL" and len(index.pred[m]) == 2)
            _match(all(kind(p) == "MATMUL" for p in index.pred[m]))
            score_mults.add(m)
        _match(len(score_mults) == len(exps))
        common = set.intersection(*(index.pred[m] for m in score_mults))
        _match(len(common) == 1)
        q = next(iter(common))
        ks = {next(iter(index.pred[m] - {q})) for m in score_mults}
        _match(len(ks) == len(exps) and not (ks & vs) and q not in vs)
        max_root = next(iter(max_roots))
        max_inside, max_scores = reverse_until(max_root, scores)
        _match(max_scores == scores and all(kind(u) in {"REDUCE", "SUB", "RELU", "ADD"}
                                           for u in max_inside))
        stops = {q} | ks | vs
        inside, external = reverse_until(root, stops)
        expected = ({root} | reds | dadds | mults | nadds | exps | shifts
                    | scores | score_mults | max_inside)
        _match(inside == expected and external == stops and len(inside) == 12 * len(exps) - 4)
        # After a motif matches, broken closure is unsafe input, not a skipped row.
        if any(index.succ[u] - inside for u in inside - {root}):
            raise UnsupportedStructure("attention row has an external interior compute consumer")
        incoming = sorted({t for u in inside for t in ports.inputs[u]
                           if ports.producer.get(t) not in inside})
        outgoing = sorted({t for u in inside for t in ports.outputs[u]
                           if ports.consumers[t] - inside})
        if len(outgoing) != 1 or ports.producer[outgoing[0]] != root:
            raise UnsupportedStructure("attention row needs one raw tensor exit at its final DIV")
        compute_inputs = {ports.producer[t] for t in incoming
                          if ports.producer.get(t) in index.ops}
        if compute_inputs != stops:
            raise UnsupportedStructure("unexpected raw compute input in attention row")
        kv_tensors = [t for t in incoming if ports.producer.get(t) in ks | vs]
        q_tensors = [t for t in incoming if ports.producer.get(t) == q]
        extra = [t for t in incoming if ports.producer.get(t) not in stops]
        if (len(kv_tensors) != 2 * len(exps) or len(q_tensors) != 1 or len(extra) != 1
                or ports.tensors[extra[0]]["size"] != 2):
            raise UnsupportedStructure("row boundary requires one tensor per Q/K/V and a 2-byte scalar")
        if not index.succ[q] <= inside:
            raise UnsupportedStructure("row Q projection has an external compute consumer")
        work = {p: sum(index.duration(u) for u in inside if index.ops[u]["pipe"] == p)
                for p in ("PIPE_M", "PIPE_V")}
        return {"nodes": tuple(sorted(inside)), "sink": root, "q": q,
                "k": tuple(sorted(ks)), "v": tuple(sorted(vs)), "work": work,
                "boundary_inputs": tuple(incoming), "boundary_outputs": tuple(outgoing),
                "kv_distinct_boundary_bytes": sum(ports.tensors[t]["size"] for t in kv_tensors),
                "private_q_raw_closed": all(ports.consumers[t] <= inside for t in ports.outputs[q])}

    rows = []
    for root in index.order:
        parents = sorted(index.pred[root])
        if (kind(root) != "DIV" or len(parents) != 2
                or any(kind(p) != "ADD" for p in parents)):
            continue
        for denominator, numerator in (parents, parents[::-1]):
            try:
                row = try_roles(root, denominator, numerator)
            except _NotRow:
                continue
            rows.append(row)
            break
    if not rows:
        raise UnsupportedStructure("no closed attention query row matched")
    occupied = set()
    panels = defaultdict(list)
    for row in rows:
        if occupied.intersection(row["nodes"]):
            raise UnsupportedStructure("attention row interiors overlap")
        occupied.update(row["nodes"])
        panels[(row["k"], row["v"])].append(row)
    for (ks, vs), group in panels.items():
        nodes = {u for row in group for u in row["nodes"]}
        if any(index.succ[u] - nodes for u in ks + vs):
            raise UnsupportedStructure("shared K/V has a consumer outside its recognized panel")
        if any(index.succ[u] & (nodes - set(row["nodes"]))
               for row in group for u in row["nodes"]):
            raise UnsupportedStructure("sibling attention rows are not independent")
    return rows

