"""Pure integer-DAG tests; no official compiler, response, or evaluator."""
import functools
import unittest

from src.review.p1_lazy_packet_search import Unknown, UnknownResult, search
from src.review.p1_packet_edge_bound import Resources


def zero_bound(kind, state, prefix, payload):
    return 0  # admissible for nonnegative edge costs


def cost(kind, state, payload):
    n, r = state
    if kind == "normal":
        q, s = payload
        return q * q + s + r
    if kind == "drain":
        return 2
    return 1 if payload == "merge" else 3


class LazyPacketTests(unittest.TestCase):
    def test_cooperative_stop_preserves_frontier_and_incumbent(self):
        called = []
        def exact(*args):
            called.append(args)
            return 1
        immediate = search(10**6, exact, zero_bound, budget=100,
                           should_stop=lambda: True)
        self.assertEqual(immediate['stop_reason'], 'external_stop')
        self.assertEqual(immediate['open'], 1)
        self.assertEqual(immediate['lower'], 0)
        self.assertEqual(called, [])
        # B=0 has two terminal alternatives. Stop after evaluating the first,
        # retaining both that incumbent and the unexplored second alternative.
        stopped = search(0, exact, zero_bound, budget=100,
                         should_stop=lambda: bool(called))
        self.assertEqual(stopped['stop_reason'], 'external_stop')
        self.assertEqual((stopped['lower'], stopped['upper']), (0, 1))
        self.assertEqual(stopped['open'], 1)
        self.assertIsNotNone(stopped['best_path'])
        self.assertFalse(stopped['optimal'])

    def test_resource_envelope_connection_matches_full_abstract_DAG(self):
        # This is an exact cost DEFINITION for a synthetic resource DAG,
        # not a surrogate score reported as a physical scheduling response.
        B = 4
        obj = Resources(2, 7, 3, 4, 3, 5, (B, B), 2)
        def edge(kind, state, payload):
            n, r = state
            if kind == 'normal':
                q, s = payload
                forms, _ = obj.forms(n, r, positive_s=s > 0)
                return max(a*q+b*s+c for a, b, c in forms) + (obj.gate if n else 0) + (n+q+r+s) % 3
            return max(r*obj.c, 2*r*obj.d_return) + (obj.gate if r else 0)
        def lower(kind, state, prefix, payload):
            n, r = state
            if kind == 'box':
                return obj.box(n, r, payload, prefix)['frontier_lower_bound']
            remain = B-n
            return prefix + max(remain*(obj.a+obj.c)+r*obj.c, remain*obj.b,
                                2*(remain*obj.d_whole+r*obj.d_return))
        @functools.lru_cache(None)
        def full(n, r):
            options = ([edge('terminal', (n, r), p) for p in ('merge', 'separate')]
                       if n == B else
                       [edge('normal', (n, r), (q, s)) + full(n+q, s)
                        for q in range(1, B-n+1) for s in range(q+1)])
            if r:
                options.append(edge('drain', (n, r), None) + full(n, 0))
            return min(options)
        answer = search(B, edge, lower, budget=1000)
        self.assertEqual((answer['lower'], answer['upper']), (full(0, 0), full(0, 0)))
        self.assertTrue(answer['optimal'])

    def test_matches_independent_full_enumeration(self):
        B = 3
        @functools.lru_cache(None)
        def full(n, r):
            if n == B:
                options = [cost("terminal", (n, r), p) for p in ("merge", "separate")]
            else:
                options = [cost("normal", (n, r), (q, s)) + full(n + q, s)
                           for q in range(1, B - n + 1) for s in range(q + 1)]
            if r:
                options.append(cost("drain", (n, r), None) + full(n, 0))
            return min(options)
        result = search(B, cost, zero_bound, budget=1000)
        self.assertEqual((result["lower"], result["upper"]), (full(0, 0), full(0, 0)))
        self.assertTrue(result["optimal"])

    def test_better_prefix_reopens_and_stale_work_is_ignored(self):
        def edge(kind, state, payload):
            if kind == "normal" and state == (0, 0):
                return 5 if payload == (1, 0) else 0 if payload == (1, 1) else 100
            return 0
        result = search(2, edge, zero_bound, budget=1000)
        self.assertGreaterEqual(result["reopens"], 1)
        self.assertEqual(result["upper"], 0)
        self.assertTrue(result["optimal"])

    def test_unknown_and_zero_budget_keep_lower_bound(self):
        stopped = search(2, cost, zero_bound, budget=0)
        self.assertEqual((stopped["lower"], stopped["upper"], stopped["open"]), (0, None, 1))
        self.assertFalse(stopped["optimal"])
        def uncertain(kind, state, payload):
            return Unknown if kind == "normal" and payload == (1, 0) else None
        result = search(1, uncertain, zero_bound, budget=10)
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual((result["lower"], result["upper"]), (0, None))
        for exception in (UnknownResult, TimeoutError):
            def interrupted(*_):
                raise exception('unfinished abstract oracle')
            result = search(1, interrupted, zero_bound, budget=10)
            self.assertEqual(result['unresolved'], 2)
            self.assertEqual(result['rejects'], 0)
            self.assertFalse(result['optimal'])

    def test_integer_boxes_cover_root_triangle_once(self):
        seen = []
        def edge(kind, state, payload):
            if kind == "normal" and state == (0, 0):
                seen.append(payload)
            return 1
        search(3, edge, zero_bound, budget=1000)
        self.assertEqual(sorted(seen), sorted((q, s) for q in range(1, 4)
                                           for s in range(q + 1)))

    def test_large_box_stops_before_oracle_without_losing_open_item(self):
        result = search(10**6, lambda *_: 0, zero_bound, budget=1,
                        max_expansions=10)
        self.assertEqual(result["stop_reason"], "expansion_budget")
        self.assertEqual(result["expansions"], 10)
        self.assertEqual(result["exact_calls"], 0)
        self.assertTrue(result["open_items"])
        self.assertEqual(result["lower"], 0)

    def test_unknown_edge_is_not_retried_after_better_prefix(self):
        seen = {}
        def edge(kind, state, payload):
            key = (kind, state, payload)
            seen[key] = seen.get(key, 0) + 1
            if key == ("normal", (1, 0), (1, 0)):
                return Unknown
            if kind == "normal" and state == (0, 0):
                return 5 if payload == (1, 0) else 2 if payload == (1, 1) else 100
            if kind == "terminal":
                return 100
            return 0
        def lower(kind, state, prefix, payload):
            if state == (0, 0) and kind == "box" and payload == (1, 1, 1, 1):
                return 1
            return 0
        result = search(2, edge, lower, budget=100)
        self.assertGreaterEqual(result["reopens"], 1)
        self.assertEqual(seen.get(("normal", (1, 0), (1, 0))), 1)
        self.assertGreaterEqual(result["cache_hits"], 1)
        self.assertTrue(any(item["state"] == (1, 0) for item in result["unresolved_items"]))


if __name__ == "__main__":
    unittest.main()
