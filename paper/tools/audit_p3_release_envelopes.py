"""Read pinned published profiles and recompute their algebra; no new candidates.

Does not import the compiler/model, rebuild saved Tasks, or call any evaluator.
The original Task snapshot, capacity peaks and official feasibility are not
reverified here. The output records this boundary along with input byte hashes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SHA = "3d22453deb0d2e3618f9d6cb41795ff164c6c84e"
BASE = "results/a/q3-nikolastarx/"
FAMILY = BASE + "release-envelope-model-20260925/"
COMPILER = BASE + "partial-bucket-compile-20260925/"
INPUTS = BASE + "pipeline-prefix-static-20260925/"
CHAT = "AI chats/20260924-Pro-P3-归约森林切分/"


def main():
    sources = []
    hashes = {}

    def raw(path):
        data = subprocess.run(
            ["git", "show", f"{SHA}:{path}"], cwd=ROOT,
            check=True, capture_output=True).stdout
        digest = hashlib.sha256(data).hexdigest()
        hashes[path] = digest
        sources.append(dict(commit=SHA, path=path, bytes=len(data), sha256=digest))
        return data

    def read(path):
        return json.loads(raw(path))

    family = read(FAMILY + "saved-family.json")
    structure = read(COMPILER + "structure-table.json")
    plan = read(INPUTS + "case_044_multicore_res.json")
    read(INPUTS + "certificate.json")
    example = read(COMPILER + "example-plan.json")
    word = read(COMPILER + "example-predicted-word.json")
    for path in (COMPILER + "compile.py", FAMILY + "model.py",
                 FAMILY + "task_profile.py", FAMILY + "audit_saved_family.py"):
        raw(path)  # Source identity only: never import or execute these files.
    for path, digest in hashes.items():
        key = "q3-core-nikolastarx/" + path
        if key in family["source_sha256"]:
            assert family["source_sha256"][key] == digest, path
    for key, name in (("plan", "case_044_multicore_res.json"),
                      ("certificate", "certificate.json")):
        assert structure["source_sha256"][key] == hashes[INPUTS + name]
    assert family["source_family"] == structure["family"] + " plus original full prefix"
    assert not any(family["calls"].values())
    assert not any(structure["calls"].values())
    assert all(row["status"] == "static_pass" for row in structure["breakpoints"])

    profiles = []
    for row in family["rows"]:
        transfers = row["transfers"]
        compute = row["total_compute"]
        sums = [0]
        for transfer in transfers:
            work = transfer["fixed_service"]
            before = transfer["compute_before_first_use"]
            assert type(work) is int and work > 0
            assert type(before) is int and 0 <= before <= compute
            sums.append(sums[-1] + work)
        assert sums[-1] == row["fixed_input_work"]
        # Direct coefficient definitions, not a call to the published selector.
        suffix = [max(sums[i + 1] - transfers[i]["compute_before_first_use"]
                      for i in range(j, len(transfers)))
                  for j in range(len(transfers))]
        lags = {}
        for j, transfer in enumerate(transfers):
            key = transfer["release_key"]
            if key is not None:
                coefficient = compute - sums[j] + suffix[j]
                lags[key] = max(lags.get(key, coefficient), coefficient)
        intercept = max([compute, compute + max([0, *suffix]), *lags.values()])
        signature = dict(base=intercept, lags=lags)
        assert signature == row["signature"], row["h"]
        profiles.append(dict(h=row["h"], q=row["q"], signature=signature))

    domain = set(profiles[0]["signature"]["lags"])
    assert all(set(p["signature"]["lags"]) == domain for p in profiles)
    for row, profile in zip(family["rows"], profiles):
        a = profile["signature"]
        dominated_by, equivalent = [], []
        for other in profiles:
            if other["h"] == profile["h"]:
                continue
            b = other["signature"]
            if a == b:
                equivalent.append(other["h"])
            elif b["base"] <= a["base"] and all(b["lags"][k] <= a["lags"][k] for k in domain):
                dominated_by.append(other["h"])
        assert dominated_by == row["strictly_model_dominated_by"]
        assert equivalent == row["same_model_signature_as"]
        profile["model_dominated_by"] = dominated_by
    frontier = [p for p in profiles if not p["model_dominated_by"]]
    assert [p["h"] for p in frontier] == [2, 15, 17]
    assert [(p["h"], p["q"]) for p in profiles[:-1]] == [
        (r["h"], r["head_cold_count"]) for r in structure["breakpoints"]]

    assert set(example) == set(plan) == {"node_to_subgraph", "core_schedules"}
    assert set(example["node_to_subgraph"]) == set(plan["node_to_subgraph"])
    for core in (0, 1, 3, 4):
        assert example["core_schedules"][core] == plan["core_schedules"][core]
    assert word["head_count"] == structure["example_h"] == 10
    assert word["pilot_activation_positions"] == [4, 5]

    manifest = read(CHAT + "manifest-r07-bb41cb93.json")
    answer = raw(CHAT + "FINAL-r07-bb41cb93.rendered.txt")
    entry = next(x for x in manifest["files"]
                 if x["path"] == "FINAL-r07-bb41cb93.rendered.txt")
    assert len(answer) == entry["bytes"]
    assert hashlib.sha256(answer).hexdigest() == entry["sha256"]
    output = dict(
        schema="p3-paper-release-envelope-audit-v1", source_files=sources,
        fixed_commit=SHA, profiles=profiles, model_frontier=frontier,
        example_h=10, declared_static_passes=len(structure["breakpoints"]),
        pro_message_id=manifest["assistant_message_id"],
        pro_attachment_status=manifest["attachment_status"],
        new_calls=dict(solver=0, Task=0, Step=0, E0=0, candidates=0),
        limitations=[
            "Eight published transfer profiles were used to recompute coefficient arithmetic and model dominance only.",
            "The compiler and selector source were hashed but not executed here; their published tests were not rerun and no new candidate was constructed.",
            "The full Task snapshot was not read or rebuilt; capacity peaks, dependency acyclicity and upstream release ordering remain attributed published checks.",
            "Model dominance requires identical independent nonnegative release variables and fixed services; not an official pruning certificate or Makespan score.",
            "The R7 visible-answer byte hash was checked; its code/certificate attachments were not acquired or executed and its nine tests remain author-reported."])
    target = ROOT / "paper/drafts/p3-release-envelope-audit.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(profiles=len(profiles), frontier_h=[p["h"] for p in frontier],
                          source_files=len(sources), new_calls=output["new_calls"])))


if __name__ == "__main__":
    main()
