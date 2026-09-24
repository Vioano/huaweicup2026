import copy
import unittest

from src.q3.cache_trace_audit import analyze


def fixture():
    result = {"problem": 3, "cache_mode": "read_only", "cache_capacity_bytes": 5,
              "cache_events": [], "per_core_timeline": [],
              "cache_stats": {"hit_bytes": 3, "miss_bytes": 18,
                              "copy_in_hits": 1, "copy_in_misses": 5},
              "cache_final_entries": [{"tensor_id": 1, "size_bytes": 3}],
              "cache_used_bytes_final": 3}
    ops = {0: [], 1: []}
    for oid, tid, start, end, hit in [(1, 1, 0, 2, False), (2, 1, 1, 4, False),
                                     (3, 1, 5, 6, True), (4, 2, 6, 7, False),
                                     (5, 1, 9, 10, False), (6, 3, 11, 12, False)]:
        core = int(oid == 2)
        ops[core].append({"op_id": oid, "op": "COPY_IN", "cache_tensor_id": tid,
                    "start": start, "end": end, "cache_hit": hit,
                    "memory_path": "CACHE_READ" if hit else "DDR"})
        result["cache_events"].append({"time": start, "event": "hit" if hit else "miss",
                                        "tensor_id": tid, "size_bytes": 6 if tid == 3 else 3,
                                        "core_id": core, "op_id": oid})
    for time, tid, oid, evicted in [(2, 1, 1, []), (7, 2, 4, [1]), (10, 1, 5, [2])]:
        result["cache_events"].append({"time": time, "event": "insert", "tensor_id": tid,
                                        "size_bytes": 3, "core_id": 0, "op_id": oid,
                                        "evicted_tensor_ids": evicted, "used_bytes": 3})
    result["cache_events"].sort(key=lambda e: e["time"])
    result["per_core_timeline"] = [{"core_id": core, "ops": entries}
                                   for core, entries in ops.items()]
    return result


class CacheTraceAuditTests(unittest.TestCase):
    def test_separates_overlapping_miss_from_eviction_and_oversize(self):
        row = analyze(fixture())
        self.assertEqual([row[f"{kind}_bytes"] for kind in
                          ("hit", "first_access", "miss_in_flight", "after_eviction", "oversize")],
                         [3, 6, 3, 3, 6])
        self.assertEqual(row["fifo_evictions"], 2)
        self.assertEqual(row["fifo_reinsertions"], 1)

    def test_rejects_corrupted_hit_and_summary(self):
        for change in ("event", "summary", "final"):
            result = fixture()
            if change == "event":
                next(e for e in result["cache_events"] if e["event"] == "hit")["event"] = "miss"
            elif change == "summary":
                result["cache_stats"]["hit_bytes"] += 1
            else:
                result["cache_final_entries"][0]["tensor_id"] = 9
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze(result)

    def test_rejects_non_fifo_eviction(self):
        result = copy.deepcopy(fixture())
        next(e for e in result["cache_events"] if e.get("evicted_tensor_ids"))["evicted_tensor_ids"] = [9]
        with self.assertRaisesRegex(ValueError, "FIFO"):
            analyze(result)

    def test_duplicate_timeline_key_is_rejected(self):
        result = fixture()
        result["per_core_timeline"][0]["ops"].append(result["per_core_timeline"][0]["ops"][0])
        with self.assertRaisesRegex(ValueError, "duplicate timeline"):
            analyze(result)

    def test_zero_byte_insert_binding_scope_is_explicit(self):
        result = {"problem": 3, "cache_mode": "read_only", "cache_capacity_bytes": 5,
                  "per_core_timeline": [{"core_id": 0, "ops": [
                      {"op_id": 1, "op": "COPY_IN", "start": 0, "end": 1}]}],
                  "cache_events": [{"time": 1, "event": "insert", "tensor_id": 7,
                                    "size_bytes": 0, "core_id": 0, "op_id": 1,
                                    "used_bytes": 0, "evicted_tensor_ids": []}],
                  "cache_stats": {"hit_bytes": 0, "miss_bytes": 0,
                                  "copy_in_hits": 0, "copy_in_misses": 0},
                  "cache_final_entries": [{"tensor_id": 7, "size_bytes": 0}],
                  "cache_used_bytes_final": 0}
        self.assertEqual(analyze(result)["zero_insert_binding_unavailable_count"], 1)
        result["per_core_timeline"][0]["ops"][0]["cache_tensor_id"] = 9
        with self.assertRaisesRegex(ValueError, "binding mismatch"):
            analyze(result)

    def test_hit_completion_can_reinsert_an_evicted_key(self):
        result = {"problem": 3, "cache_mode": "read_only", "cache_capacity_bytes": 5,
                  "per_core_timeline": [
                      {"core_id": 0, "ops": [
                          {"op_id": 1, "op": "COPY_IN", "cache_tensor_id": 1,
                           "start": 0, "end": 2, "cache_hit": False, "memory_path": "DDR"},
                          {"op_id": 2, "op": "COPY_IN", "cache_tensor_id": 1,
                           "start": 3, "end": 9, "cache_hit": True, "memory_path": "CACHE_READ"}]},
                      {"core_id": 1, "ops": [
                          {"op_id": 3, "op": "COPY_IN", "cache_tensor_id": 2,
                           "start": 4, "end": 5, "cache_hit": False, "memory_path": "DDR"}]}],
                  "cache_events": [],
                  "cache_stats": {"hit_bytes": 3, "miss_bytes": 6,
                                  "copy_in_hits": 1, "copy_in_misses": 2},
                  "cache_final_entries": [{"tensor_id": 1, "size_bytes": 3}],
                  "cache_used_bytes_final": 3}
        for now, kind, tid, core, oid, evicted in [
                (0, "miss", 1, 0, 1, []), (2, "insert", 1, 0, 1, []),
                (3, "hit", 1, 0, 2, []), (4, "miss", 2, 1, 3, []),
                (5, "insert", 2, 1, 3, [1]), (9, "insert", 1, 0, 2, [2])]:
            result["cache_events"].append({"time": now, "event": kind, "tensor_id": tid,
                                           "size_bytes": 3, "core_id": core, "op_id": oid,
                                           "evicted_tensor_ids": evicted, "used_bytes": 3})
        self.assertEqual(analyze(result)["fifo_reinsertions"], 1)


if __name__ == "__main__":
    unittest.main()
