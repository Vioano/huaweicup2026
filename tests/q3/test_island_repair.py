"""Falsifiable compute-model examples, independent timing oracle; zero E0."""
import copy
import random
import unittest

from src.q3.attention_rows import construct as rows_construct
from src.q3.construct import Index
from src.q3.island_repair import construct
from tests.q3.test_attention_rows import GraphBuilder, attention_graph, dag_timing, plan_words


def ffn_fixture(count=3, work=2000, vector=10):
    builder = GraphBuilder()
    source, weight = builder.source(), builder.source()
    jobs = []
    for _ in range(count):
        a = builder.op("MATMUL", "PIPE_M", work, [source, weight])
        b = builder.op("SIGMOID", "PIPE_V", vector, [a[1]])
        c = builder.op("MUL", "PIPE_V", vector, [a[1], b[1]])
        d = builder.op("MATMUL", "PIPE_M", work, [c[1], weight])
        builder.op("COPY_OUT", "PIPE_MTE3", 0, [d[1]], pos="DDR")
        jobs.append((a, b, c, d))
    return builder, jobs


def grouped_plan(index, jobs, owners, cores):
    words = []
    for core in range(cores):
        group = [job for job, owner in zip(jobs, owners) if owner == core]
        words.append([job[0][0] for job in group]
                     + [op[0] for job in group for op in job[1:3]]
                     + [job[3][0] for job in group])
    return {"node_to_subgraph": {str(u): u for u in index.order}, "core_schedules": words}


class IslandRepairTests(unittest.TestCase):
    def check(self, index, anchor, delay):
        raw = copy.deepcopy(index.graph)
        old_plan = copy.deepcopy(anchor)
        candidate, metadata = construct(index, anchor, delay)
        _, before = dag_timing(index, plan_words(anchor), delay)
        _, after = dag_timing(index, plan_words(candidate), delay)
        self.assertEqual(max(before.values()), metadata["initial_compute_bound"])
        self.assertLessEqual(max(after.values()), max(before.values()))
        self.assertEqual(index.graph, raw)
        self.assertEqual(anchor, old_plan)
        self.assertEqual(candidate["node_to_subgraph"], anchor["node_to_subgraph"])
        self.assertEqual(metadata["official_evaluations"], 0)
        for block in metadata["blocks"]:
            for port in block.get("exits", []):
                self.assertLessEqual(port["after"], port["before"])
        return candidate, metadata

    def test_three_ffns_one_tail_migration_beats_whole_home(self):
        builder, jobs = ffn_fixture()
        index = Index(builder.graph)
        anchor = grouped_plan(index, jobs, [0, 0, 1], 2)
        candidate, meta = self.check(index, anchor, 500)
        self.assertEqual(meta["initial_compute_bound"], 8000)
        self.assertEqual(meta["candidate_compute_bound"], 6520)
        self.assertTrue(meta["returned_candidate"])
        self.assertEqual([b["status"] for b in meta["blocks"]], ["unchanged", "island", "unchanged"])
        owner = {u: c for c, word in enumerate(plan_words(candidate)) for u in word}
        self.assertEqual(owner[jobs[1][-1][0]], 1)
        self.assertEqual({owner[op[0]] for op in jobs[1][:-1]}, {0})

    def test_short_work_cannot_pay_remote_lag(self):
        builder, jobs = ffn_fixture(work=30, vector=2)
        index = Index(builder.graph)
        anchor = grouped_plan(index, jobs, [0, 0, 1], 2)
        candidate, meta = self.check(index, anchor, 500)
        self.assertEqual(candidate, anchor)
        self.assertFalse(meta["returned_candidate"])

    def test_all_external_compute_consumers_and_copy_outputs_are_pinned(self):
        builder, jobs = ffn_fixture()
        tail = jobs[1][-1]
        other_copy = builder.op("COPY_OUT", "PIPE_MTE3", 0, [tail[1]], pos="DDR")
        x = builder.op("RELU", "PIPE_V", 1, [tail[1]])
        y = builder.op("RELU", "PIPE_V", 1, [tail[1]])
        index = Index(builder.graph)
        anchor = grouped_plan(index, jobs, [0, 0, 1], 2)
        anchor["core_schedules"][0].append(x[0])
        anchor["core_schedules"][1].append(y[0])
        _, meta = self.check(index, anchor, 500)
        record = next(b for b in meta["blocks"] if b["sink"] == tail[0])
        self.assertEqual({p["consumer"] for p in record["exits"]}, {None, x[0], y[0]})
        self.assertEqual(sum(p["consumer"] is None for p in record["exits"]), 2)
        self.assertNotIn(other_copy[0], index.ops)

    def test_attention_keeps_original_reductions_and_individual_releases(self):
        builder, _ = attention_graph()
        index = Index(builder.graph)
        for delay in (0, 7, 500):
            anchor, _ = rows_construct(index, 3, delay, placement_mode="gap", final_order="placement")
            self.check(index, anchor, delay)

    def test_seeded_small_ffn_schedules_have_no_proxy_regression(self):
        rng = random.Random(20260925)
        for _ in range(30):
            count, cores = rng.randrange(1, 9), rng.randrange(1, 5)
            builder, jobs = ffn_fixture(count, rng.randrange(1, 250), rng.randrange(1, 80))
            index = Index(builder.graph)
            owners = [rng.randrange(cores) for _ in jobs]
            anchor = grouped_plan(index, jobs, owners, cores)
            _, meta = self.check(index, anchor, rng.randrange(100))
            self.assertLessEqual(meta["local_trials"], count * cores)


if __name__ == "__main__":
    unittest.main()
