"""Static leaf-round tiling for guarded Cartesian left-deep reduction forests.

Q and D are algebraic scheduling proxies, not Step2/Step3 or Cache models.
No official evaluator is called here.
"""
from __future__ import annotations

from collections import defaultdict

from .construct import UnsupportedStructure, derive_multicore_plan
from .forest_memory_order import _original_tree, construct as forest_order
from .forest_reuse_grid import recognize


def _capacity(value):
    if isinstance(value, dict):
        value = value.get("L1")
    if type(value) is not int or value <= 0:
        raise ValueError("positive integer L1 capacity required")
    return value


def _chains(index, model):
    """Return cell -> (ordered M leaves, ordered original ADDs), plus a,b,s."""
    sizes, output_tensors, records, _ = _original_tree(index)
    if len(records) != len(index.components):
        raise UnsupportedStructure("component/tree count mismatch")
    axes = model["axes"]
    groups = model["group_tensor_ids"]
    group_tids = [set(group) for group in groups]
    axis_tids = [{tid for group in axes[axis] for tid in group_tids[group]}
                 for axis in (0, 1)]
    if axis_tids[0] & axis_tids[1]:
        raise UnsupportedStructure("input axes overlap")
    tensors = {t["id"]: t for t in index.graph["tensors"]}
    all_ops = {o["id"]: o for o in index.graph["ops"]}
    incoming = defaultdict(set)
    producers = defaultdict(set)
    for edge in index.graph["edges"]:
        if edge["target"] in index.ops and edge["source"] in tensors:
            incoming[edge["target"]].add(edge["source"])
        if edge["target"] in tensors and edge["source"] in all_ops:
            producers[edge["target"]].add(edge["source"])
    for tid in axis_tids[0] | axis_tids[1]:
        source = producers[tid]
        if len(source) != 1 or all_ops[next(iter(source))]["op"] != "COPY_IN":
            raise UnsupportedStructure("shared input requires one original COPY_IN")

    leaf_words = {}
    inputs = [{}, {}]
    pipe_words = None
    output_size = None
    leaf_count = None
    row_pos = {group: i for i, group in enumerate(axes[0])}
    col_pos = {group: j for j, group in enumerate(axes[1])}
    cells = sorted(model["cells"].items(),
                   key=lambda item: (row_pos[item[0][0]], col_pos[item[0][1]]))
    for (row_group, col_group), cid in cells:
        record = records[cid]
        root, children = record["root"], record["children"]
        leaves_reverse, adds_reverse, cursor = [], [], root
        while index.ops[cursor]["op"] == "ADD":
            if index.ops[cursor]["pipe"] != "PIPE_V" or len(children[cursor]) != 2:
                raise UnsupportedStructure("requires binary PIPE_V ADD chain")
            left, right = children[cursor]
            m = [u for u in (left, right) if index.ops[u]["op"] == "MATMUL"]
            v = [u for u in (left, right) if index.ops[u]["op"] == "ADD"]
            adds_reverse.append(cursor)
            if len(m) == 2 and not v:
                # The bottom ADD is symmetric. Establish an arbitrary label
                # in the first cell, then align other cells by original tensor
                # identity rather than by unrelated op IDs.
                pair = sorted(m)
                choices = (pair, pair[::-1])
                selected = None
                for choice in choices:
                    compatible = True
                    for t, leaf in enumerate(choice):
                        for axis, group in enumerate((row_group, col_group)):
                            matches = incoming[leaf] & group_tids[group]
                            known = inputs[axis].get((group, t))
                            if len(matches) != 1 or (known is not None and known not in matches):
                                compatible = False
                    if compatible:
                        selected = choice
                        break
                if selected is None:
                    raise UnsupportedStructure("bottom leaf pair cannot align by shared input")
                leaves = selected + list(reversed(leaves_reverse))
                adds = list(reversed(adds_reverse))
                break
            if len(m) != 1 or len(v) != 1:
                raise UnsupportedStructure("requires a strict left-deep ADD chain")
            leaves_reverse.append(m[0])
            cursor = v[0]
        else:
            raise UnsupportedStructure("root must be ADD")
        if len(leaves) < 2 or len(adds) != len(leaves) - 1:
            raise UnsupportedStructure("invalid leaf/ADD counts")
        if set(leaves + adds) != record["members"]:
            raise UnsupportedStructure("tree contains extra or missing compute ops")
        if any(index.ops[u]["op"] != "MATMUL" or
               index.ops[u]["pipe"] != "PIPE_M" or children[u]
               for u in leaves):
            raise UnsupportedStructure("requires independent PIPE_M MATMUL leaves")
        for u in adds:
            expected = {output_tensors[child][0] for child in children[u]}
            if incoming[u] != expected:
                raise UnsupportedStructure("ADD must read exactly its two tree children")
        word = (tuple(index.ops[u]["cycles"] for u in leaves),
                tuple(index.ops[u]["cycles"] for u in adds))
        if pipe_words is None:
            pipe_words = word
        elif pipe_words != word:
            raise UnsupportedStructure("leaf and ADD pipe work differs across cells")
        if leaf_count is None:
            leaf_count = len(leaves)
        elif leaf_count != len(leaves):
            raise UnsupportedStructure("leaf counts differ across cells")
        for u in leaves + adds:
            tid = output_tensors[u][0]
            tensor = tensors[tid]
            if tensor["pos"] != "L1" or sizes[tid] <= 0:
                raise UnsupportedStructure("all compute outputs must be positive L1 tensors")
            if output_size is None:
                output_size = sizes[tid]
            elif output_size != sizes[tid]:
                raise UnsupportedStructure("compute output sizes differ")
        for t, u in enumerate(leaves):
            ports = incoming[u]
            if len(ports) != 2:
                raise UnsupportedStructure("MATMUL must read exactly two tensors")
            for axis, group in enumerate((row_group, col_group)):
                matches = ports & group_tids[group]
                if len(matches) != 1:
                    raise UnsupportedStructure("MATMUL input does not match both grid axes")
                tid = next(iter(matches))
                if tensors[tid]["pos"] != "L1" or sizes[tid] <= 0:
                    raise UnsupportedStructure("shared input must be a positive L1 tensor")
                key = (group, t)
                previous = inputs[axis].setdefault(key, tid)
                if previous != tid:
                    raise UnsupportedStructure("leaf ordinal uses inconsistent shared input")
            if not ports <= axis_tids[0] | axis_tids[1]:
                raise UnsupportedStructure("MATMUL has another input")
        leaf_words[cid] = (leaves, adds)

    # Every ordinal and axis-group must appear. Uniform per-leaf sizes make D
    # an exact input-byte count within the ideal tile model.
    for axis in (0, 1):
        expected = {(g, t) for g in axes[axis] for t in range(leaf_count)}
        if set(inputs[axis]) != expected:
            raise UnsupportedStructure("incomplete ordinal/group input coverage")
        for group in axes[axis]:
            ordinal_tids = {inputs[axis][group, t] for t in range(leaf_count)}
            if ordinal_tids != group_tids[group] or len(ordinal_tids) != leaf_count:
                raise UnsupportedStructure("one distinct original input required per leaf ordinal")
    a_sizes = {sizes[t] for t in inputs[0].values()}
    b_sizes = {sizes[t] for t in inputs[1].values()}
    if len(a_sizes) != 1 or len(b_sizes) != 1:
        raise UnsupportedStructure("requires uniform input sizes within each axis")
    return leaf_words, a_sizes.pop(), b_sizes.pop(), output_size, leaf_count


def _tiles(model, owner, p, q):
    axes = model["axes"]
    row_pos = {group: i for i, group in enumerate(axes[0])}
    col_pos = {group: j for j, group in enumerate(axes[1])}
    bucket = defaultdict(list)
    for (rg, cg), cid in model["cells"].items():
        i, j = row_pos[rg], col_pos[cg]
        bucket[(owner[cid], i // p, j // q)].append((i, j, cid))
    return bucket


def transform(index, plan, capacity):
    """Reorder a singleton plan; preserve op/subgraph mapping and op/core owner."""
    c = _capacity(capacity)
    view = derive_multicore_plan(index.graph, plan)
    if any(len(nodes) != 1 for nodes in view["nodes_by_subgraph"].values()):
        raise UnsupportedStructure("requires singleton subgraphs")
    model = recognize(index)
    words, a, b, s, leaf_count = _chains(index, model)
    owner = {}
    for cid, component in enumerate(index.components):
        cores = {view["core_by_subgraph"][view["mapping"][u]] for u in component}
        if len(cores) != 1:
            raise UnsupportedStructure("a tree is split across cores")
        owner[cid] = next(iter(cores))
    m, n = map(len, model["axes"])
    best = None
    for p in range(1, m + 1):
        for q in range(1, n + 1):
            tiles = _tiles(model, owner, p, q)
            d = 0
            qmax = 0
            for cells in tiles.values():
                rows = len({i for i, _, _ in cells})
                cols = len({j for _, j, _ in cells})
                d += a * rows + b * cols
                qmax = max(qmax, (2 * len(cells) + 1) * s + a * rows + b * cols)
            if qmax > c:
                continue
            key = (d, qmax, p, q)
            if best is None or key < best[0]:
                best = (key, tiles)
    if best is None:
        raise UnsupportedStructure("no tile satisfies the ideal layer frontier bound")
    (d, qmax, p, q), tiles = best
    per_core = [[] for _ in range(view["num_cores"])]
    for (core, _, _), cells in sorted(tiles.items()):
        cells = sorted(cells)
        for t in range(leaf_count):
            per_core[core].extend(words[cid][0][t] for _, _, cid in cells)
            if t:
                per_core[core].extend(words[cid][1][t - 1] for _, _, cid in cells)
    mapping = dict(plan["node_to_subgraph"])
    candidate = {"node_to_subgraph": mapping,
                 "core_schedules": [[view["mapping"][u] for u in seq]
                                    for seq in per_core]}
    updated = derive_multicore_plan(index.graph, candidate)
    if updated["mapping"] != view["mapping"] or updated["core_by_subgraph"] != view["core_by_subgraph"]:
        raise AssertionError("leaf tile changed mapping or ownership")
    if {u for seq in per_core for u in seq} != set(index.ops) or sum(map(len, per_core)) != len(index.ops):
        raise AssertionError("leaf tile lost or duplicated an operation")
    return candidate, {
        "strategy": "cartesian_leaf_tile", "axis_sizes": [m, n],
        "leaf_count": leaf_count, "tile_shape": [p, q],
        "ideal_input_bytes_per_leaf_round": d,
        "ideal_max_layer_frontier_bytes": qmax, "l1_capacity_bytes": c,
        "input_sizes_bytes": [a, b], "compute_output_size_bytes": s,
        "tiles_by_core": [sum(key[0] == core for key in tiles) for core in range(view["num_cores"])],
        "selection": "minimize exact owner-intersection tile D, then Qmax,p,q; algebra only",
        "scope": "ideal current-layer frontier; not Step2 spill, Step3 address, Cache, or Makespan guarantee",
        "official_evaluations": 0,
    }


def construct(index, cores, capacity):
    """Use forest_memory_order's actual whole-tree owner as the input plan."""
    base, _ = forest_order(index, cores)
    plan, meta = transform(index, base, capacity)
    meta["base_strategy"] = "forest_memory_order"
    return plan, meta
