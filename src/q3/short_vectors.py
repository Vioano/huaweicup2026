"""Pure structural selection of short V regions; no official evaluation.

The work threshold is the configured cross-core release delay, not a fitted
constant. The small isolated-region theorem does not predict full-graph E0.
The caller must validate the quotient after combining these regions with its
existing capsules: a V-only weak component need not be DAG-convex.
"""


def regions(index, available, cross_delay):
    """Return maximal available V components with total positive work <= delay.

    Discovery is O(V+E). No subdivision is tried when a component is too large.
    Nodes are returned in the supplied original topological order.
    """
    if type(cross_delay) is not int or cross_delay < 0:
        raise ValueError("cross_delay must be a nonnegative integer")
    eligible = {u for u in available if index.ops[u]["pipe"] == "PIPE_V"}
    remaining = set(eligible)
    group_of, groups = {}, []
    for seed in index.order:
        if seed not in remaining:
            continue
        remaining.remove(seed)
        group = []
        stack = [seed]
        while stack:
            u = stack.pop()
            group.append(u)
            for v in index.pred[u] | index.succ[u]:
                if v in remaining:
                    remaining.remove(v)
                    stack.append(v)
        if len(group) < 2 or sum(index.duration(u) for u in group) > cross_delay:
            continue
        j = len(groups)
        groups.append([])
        group_of.update((u, j) for u in group)
    for u in index.order:
        if u in group_of:
            groups[group_of[u]].append(u)
    return [tuple(group) for group in groups]
