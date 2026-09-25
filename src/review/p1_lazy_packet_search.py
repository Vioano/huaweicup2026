"""Pure abstract-cost lazy packet DAG search; no Task or E0 integration.

The caller supplies admissible full-path bounds. No claim about their validity
or about official scores follows from this controller.
"""
from __future__ import annotations

import heapq
from itertools import count

Unknown = object()


class UnknownResult(Exception):
    """An exact oracle may raise this instead of returning Unknown."""


def search(B, exact, bound, budget, incumbent=None, max_expansions=10000,
           should_stop=None):
    """Search (n,r) with lazy integer boxes and a scalar abstract cost.

    ``exact(kind,state,payload)`` returns nonnegative int, None (proved
    unsupported), or Unknown. Payload is (q,s), None for drain, or terminal
    policy string. ``bound(kind,state,prefix,payload)`` is a caller-certified
    lower bound on a *complete* path through that item.
    ``should_stop()`` optionally checks a wall/resource stop between bounded
    operations. It is cooperative, not a substitute for an external supervisor.
    """
    if type(B) is not int or B < 0 or type(budget) is not int or budget < 0:
        raise ValueError("B and oracle budget must be nonnegative integers")
    if type(max_expansions) is not int or max_expansions < 0:
        raise ValueError("max_expansions must be a nonnegative integer")
    if incumbent is None:
        upper, best = None, None
    else:
        upper, best = incumbent
        if type(upper) is not int or upper < 0 or best is None:
            raise ValueError("incumbent needs a proved nonnegative abstract cost/path")
    serial = count()
    heap, unresolved, exact_cache = [], [], {}
    states = {(0, 0): (0, 0, ())}  # prefix, revision, path
    stats = dict(exact_calls=0, cache_hits=0, expansions=0,
                 box_splits=0, reopens=0, rejects=0, unknowns=0)
    stop_reason = "exhausted"

    def push(kind, state, prefix, revision, payload):
        value = bound(kind, state, prefix, payload)
        if type(value) is not int or value < 0:
            raise ValueError("bound must be a nonnegative integer")
        heapq.heappush(heap, (value, next(serial), kind, state, revision, payload))

    def expand(state):
        prefix, revision, _ = states[state]
        n, r = state
        if r:
            push("drain", state, prefix, revision, None)
        if n == B:
            for policy in ("merge", "separate"):
                push("terminal", state, prefix, revision, policy)
        else:
            push("box", state, prefix, revision, (1, B - n, 0, B - n))

    def live(item):
        _, _, _, state, revision, _ = item
        return states[state][1] == revision

    expand((0, 0))
    while heap:
        if should_stop is not None and should_stop():
            stop_reason = "external_stop"
            break  # no item has been removed; retain the entire live frontier
        item = heapq.heappop(heap)
        if not live(item):
            continue
        lower, _, kind, state, revision, payload = item
        if upper is not None and lower >= upper:
            heapq.heappush(heap, item)
            stop_reason = "incumbent_bound"
            break
        if stats["expansions"] >= max_expansions:
            heapq.heappush(heap, item)
            stop_reason = "expansion_budget"
            break
        prefix, _, path = states[state]
        if kind == "box" and stats["exact_calls"] >= budget:
            heapq.heappush(heap, item)
            stop_reason = "oracle_budget"
            break
        stats["expansions"] += 1
        if kind == "box":
            qlo, qhi, slo, shi = payload
            if slo > qhi:
                continue  # empty intersection with s <= q
            if qlo != qhi or slo != shi:
                stats["box_splits"] += 1
                if qhi - qlo >= shi - slo and qlo != qhi:
                    mid = (qlo + qhi) // 2
                    children = ((qlo, mid, slo, shi), (mid + 1, qhi, slo, shi))
                else:
                    mid = (slo + shi) // 2
                    children = ((qlo, qhi, slo, mid), (qlo, qhi, mid + 1, shi))
                for child in children:
                    if child[2] <= child[1]:
                        push("box", state, prefix, revision, child)
                continue
            if slo > qlo:
                continue
            kind, payload = "normal", (qlo, slo)
        exact_key = (kind, state, payload)
        if exact_key in exact_cache:
            cost = exact_cache[exact_key]
            stats["cache_hits"] += 1
        else:
            if stats["exact_calls"] >= budget:
                stats["expansions"] -= 1
                heapq.heappush(heap, item)
                stop_reason = "oracle_budget"
                break
            try:
                cost = exact(kind, state, payload)
            except (UnknownResult, TimeoutError):
                cost = Unknown
            stats["exact_calls"] += 1
            exact_cache[exact_key] = cost
        if cost is Unknown:
            stats["unknowns"] += 1
            unresolved.append(item)
            continue
        if cost is None:
            stats["rejects"] += 1
            continue
        if type(cost) is not int or cost < 0:
            raise ValueError("exact oracle returned invalid cost")
        action = (kind, state, payload)
        candidate = prefix + cost
        if kind == "terminal":
            if upper is None or candidate < upper:
                upper, best = candidate, path + (action,)
            continue
        n, r = state
        target = (n + payload[0], payload[1]) if kind == "normal" else (n, 0)
        previous = states.get(target)
        if previous is None or candidate < previous[0]:
            if previous is not None:
                stats["reopens"] += 1
            states[target] = (candidate, 0 if previous is None else previous[1] + 1,
                              path + (action,))
            expand(target)
    live_bounds = [item[0] for item in heap if live(item)]
    live_bounds += [item[0] for item in unresolved if live(item)]
    if upper is not None:
        live_bounds.append(upper)
    lower = min(live_bounds) if live_bounds else None
    def detail(item):
        value, _, kind, state, revision, payload = item
        return dict(kind=kind, state=state, payload=payload,
                    prefix=states[state][0], bound=value, revision=revision)
    open_items = [detail(item) for item in heap if live(item)]
    unresolved_items = [detail(item) for item in unresolved if live(item)]
    return dict(best_path=best, lower=lower, upper=upper,
                optimal=upper is not None and lower == upper,
                unresolved=len(unresolved_items), open=len(open_items),
                open_items=open_items, unresolved_items=unresolved_items,
                stop_reason=stop_reason, **stats)
