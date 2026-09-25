"""Pure artifact and policy audit tests; no solver/evaluator process is run."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.q3 import fifth_core_full500_runner as runner


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, separators=(",", ":")).encode() + b"\n"
    if str(path).endswith(".gz"):
        raw = gzip.compress(raw, mtime=0)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


class Full500AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "results/a/q3-nikolastarx/run/cells/001-k1-fixed"
        self.evidence = self.folder / "evidence"
        self.graph_sha = put(self.root / "data/raw/a/official/data/case_001.json", {"nodes": []})
        self.config_sha = put(self.root / "data/raw/a/official/data/config.txt", {"config": True})
        self.old = {"node_to_subgraph": {"1": 0}, "core_schedules": [[0]]}
        self.p3 = {"scene": "B", "problem": 3, "cache_mode": "read_only",
                   "num_cores": 1, "makespan": 100}
        self.plan_sha = put(self.folder / "case_001_multicore_res.json", self.old)
        self.result_sha = put(self.evidence / "result.json.gz", self.p3)
        psha = put(self.evidence / "seed/plan.json", self.old)
        rsha = put(self.evidence / "seed/result.json.gz", self.p3)
        self.candidate = {"name": "seed", "strategy": "seed_strategy", "status": "ok",
                          "makespan": 100, "artifacts": {"plan": {"path": "seed/plan.json", "sha256": psha},
                                                           "result": {"path": "seed/result.json.gz", "sha256": rsha}}}
        self.receipt = {"status": "complete", "strategy": "seed_strategy", "makespan": 100,
                        "plan_sha256": self.plan_sha, "result_sha256": self.result_sha,
                        "graph_sha256": self.graph_sha, "config_sha256": self.config_sha,
                        "official_e0_calls": 1, "official_p3_calls": 1, "official_p2_calls": 0,
                        "candidates": [self.candidate],
                        "selection": {"fifth_core_policy": {"status": "skip"}}}
        self.ledger = [{"ordinal": 0, "phase": "p3", "status": "ok", "plan_sha256": self.plan_sha}]
        self.job = {"case_id": "001", "cores": 1, "e0_call_limit": 3}

    def finish(self):
        put(self.evidence / "receipt.json", self.receipt)
        put(self.evidence / "evaluations.json", self.ledger)
        for e in self.ledger:
            plan = self.old if e["plan_sha256"] == self.plan_sha else self.new
            put(self.evidence / f"evaluated-plan-{e['ordinal']}-{e['phase']}.json", plan)

    def test_non_five_cell_is_complete_p3_but_unpaired_g(self):
        self.finish()
        _, audited, refs = runner.validate_result(self.folder, self.job, self.root)
        self.assertEqual(audited["runner_paired_audit"]["status"], "missing_same_plan_p2")
        self.assertEqual(refs["plan"]["sha256"], self.plan_sha)

    def test_rejects_hidden_p2_on_non_five_cell(self):
        self.ledger.append({"ordinal": 1, "phase": "p2", "status": "ok", "plan_sha256": self.plan_sha})
        self.receipt["official_e0_calls"] = 2
        self.receipt["official_p2_calls"] = 1
        self.finish()
        with self.assertRaisesRegex(ValueError, "ledger|cap"):
            runner.validate_result(self.folder, self.job, self.root)

    def test_accepted_fifth_core_requires_exact_same_plan_p2(self):
        self.job.update(cores=5, e0_call_limit=6)
        self.p3["num_cores"] = 5
        self.new = {"node_to_subgraph": {"1": 0}, "core_schedules": [[], [], [], [], [0]]}
        new_p3 = {**self.p3, "makespan": 90}
        old_p2 = {"scene": "B", "num_cores": 5, "makespan": 120}
        new_p2 = {"scene": "B", "num_cores": 5, "makespan": 110}
        new_sha = put(self.folder / "case_001_multicore_res.json", self.new)
        new_result_sha = put(self.evidence / "result.json.gz", new_p3)
        put(self.evidence / "seed/result.json.gz", self.p3)
        new_p3_sha = put(self.evidence / "p3-fifth_core/plan.json", self.new)
        new_p3_result_sha = put(self.evidence / "p3-fifth_core/result.json.gz", new_p3)
        old_p2_sha = put(self.evidence / "p2-incumbent/plan.json", self.old)
        old_p2_result_sha = put(self.evidence / "p2-incumbent/result.json.gz", old_p2)
        new_p2_sha = put(self.evidence / "p2-fifth_core/plan.json", self.new)
        new_p2_result_sha = put(self.evidence / "p2-fifth_core/result.json.gz", new_p2)
        self.candidate["artifacts"]["result"]["sha256"] = runner.base.digest(self.evidence / "seed/result.json.gz")
        def refs(name, p, r):
            return {"plan": {"path": name + "/plan.json", "sha256": p},
                    "result": {"path": name + "/result.json.gz", "sha256": r}}
        extra = {"name": "component_contiguous_extra_core", "status": "accepted",
                 "metadata": {"rule": "fifth_rule"}, "m2_nonworse": True, "g_nonworse": True,
                 "p3": {"makespan": 90, "artifacts": refs("p3-fifth_core", new_p3_sha, new_p3_result_sha)},
                 "incumbent_p2": {"makespan": 120, "artifacts": refs("p2-incumbent", old_p2_sha, old_p2_result_sha)},
                 "fifth_core_p2": {"makespan": 110, "artifacts": refs("p2-fifth_core", new_p2_sha, new_p2_result_sha)}}
        self.receipt.update(strategy="fifth_rule", makespan=90, plan_sha256=new_sha,
                            result_sha256=new_result_sha, official_e0_calls=4,
                            official_p3_calls=2, official_p2_calls=2,
                            candidates=[self.candidate, extra],
                            selection={"fifth_core_policy": {"status": "accepted"}})
        self.ledger += [{"ordinal": 1, "phase": "p3", "status": "ok", "plan_sha256": new_sha},
                        {"ordinal": 2, "phase": "p2", "status": "ok", "plan_sha256": self.plan_sha},
                        {"ordinal": 3, "phase": "p2", "status": "ok", "plan_sha256": new_sha}]
        self.finish()
        _, audited, _ = runner.validate_result(self.folder, self.job, self.root)
        self.assertEqual(audited["runner_paired_audit"]["p2_makespan"], 110)
        extra["fifth_core_p2"]["artifacts"]["plan"]["sha256"] = old_p2_sha
        self.finish()
        with self.assertRaisesRegex(ValueError, "hash|exact P3 plan"):
            runner.validate_result(self.folder, self.job, self.root)

    def test_variable_reservation_caps(self):
        import copy
        proposal = json.loads((runner.ROOT / "results/a/q3-nikolastarx/r9f-final-full500-20260926/manifest-pilot-4-proposed.json").read_text())
        runner.validate_variable_caps(proposal)
        too_large = copy.deepcopy(proposal)
        too_large["jobs"][0]["e0_call_limit"] = 3
        with self.assertRaisesRegex(ValueError, "per-cell"):
            runner.validate_variable_caps(too_large)

    def test_failed_e0_ledger_is_terminal_even_with_fallback(self):
        self.ledger[0]["status"] = "failed"
        self.finish()
        with self.assertRaisesRegex(ValueError, "anomaly"):
            runner.validate_result(self.folder, self.job, self.root)

    def test_archived_p2_reused_only_for_identical_final_plan(self):
        p2 = {"scene": "B", "num_cores": 1, "makespan": 120}
        raw = gzip.compress(json.dumps(p2).encode(), mtime=0)
        p2_sha = hashlib.sha256(raw).hexdigest()
        control = {"sources": {"official_code_sha256": "a" * 64,
                                "p2_result_artifact_commit": "b" * 40},
                   "records": [{"case_id": "001", "cores": 1,
                                "forest_plan": {"sha256": self.plan_sha},
                                "graph_sha256": self.graph_sha, "config_sha256": self.config_sha,
                                "official_sha256": "a" * 64, "action": "reuse_existing_p2",
                                "same_plan_bytes": True,
                                "reused_p2": {"path": "results/p2.json.gz", "sha256": p2_sha,
                                              "source_plan_sha256": self.plan_sha,
                                              "historical_no_l2_makespan": 120}}]}
        receipt = {**self.receipt, "runner_paired_audit": {"status": "missing_same_plan_p2"}}
        with patch.object(runner.base, "git_bytes", return_value=raw):
            matched = runner.audited_control(control, self.job, receipt, self.root)
            self.assertEqual((matched["p2_makespan"], matched["p3_makespan"]), (120, 100))
            receipt["plan_sha256"] = "f" * 64
            with self.assertRaisesRegex(ValueError, "same-plan"):
                runner.audited_control(control, self.job, receipt, self.root)


if __name__ == "__main__":
    unittest.main()
