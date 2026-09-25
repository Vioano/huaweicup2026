"""Pure interval arithmetic over archived author R5 traces; no model replay."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = (ROOT / "AI chats/"
           "P1多Pipe链构造证明/附件/r5-P1_s6607_R5_causal_diagnosis/results")
PAIRED = (ROOT / "results/a/"
          "p1-period7-colab-20260925/run-0534Z/paired-signatures.json")
EXPECTED_PAIRED_SHA = "2a90a5b0e8b3ff19fe88a07e6580dc4899a63b7654d0d268c0941b947549c95b"


def union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end <= start:
            raise ValueError("nonpositive interval")
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def length(intervals):
    return sum(end - start for start, end in intervals)


def intersection_length(left, right):
    i = j = total = 0
    while i < len(left) and j < len(right):
        total += max(0, min(left[i][1], right[j][1]) - max(left[i][0], right[j][0]))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    paired_raw = PAIRED.read_bytes()
    if hashlib.sha256(paired_raw).hexdigest() != EXPECTED_PAIRED_SHA:
        raise ValueError("paired signature bytes differ")
    paired = json.loads(paired_raw)
    diagnosis_raw = (ARCHIVE / "diagnosis.json").read_bytes()
    diagnosis = json.loads(diagnosis_raw)
    rows = {}
    for name in ("whole_seed", "period7_seed"):
        raw = (ARCHIVE / f"{name}.json").read_bytes()
        trace = json.loads(raw)
        audit = json.loads((args.audit_dir / f"{name}-audit.json").read_text())
        expected = paired["variants"][name]["expected_model_makespan"]
        if (trace["makespan"] != expected or audit["makespan"] != expected or
                trace["variant"] != name or trace["expected_makespan"] != expected or
                trace["matched"] is not True or
                trace["oracle_sha256"] != paired["oracle_sha256"] or
                trace["signatures_sha256"] != EXPECTED_PAIRED_SHA or
                audit["saved_signatures_sha256"] != EXPECTED_PAIRED_SHA or
                audit["trace_input_sha256"] != hashlib.sha256(raw).hexdigest()):
            raise ValueError(f"{name}: paired bytes or makespan mismatch")
        ddr = union((op["start"], op["end"]) for op in trace["trace"] if op["ddr"])
        m = union((op["start"], op["end"]) for op in trace["trace"]
                  if op["core"] == 0 and op["pipe"] == "PIPE_M")
        v = union((op["start"], op["end"]) for op in trace["trace"]
                  if op["core"] == 0 and op["pipe"] == "PIPE_V")
        overlap = intersection_length(m, v)
        mv_union = length(m) + length(v) - overlap
        computed = dict(DDR_busy_union=length(ddr),
                        DDR_no_request_window_length=expected - length(ddr),
                        core0_MV_overlap=overlap,
                        core0_MV_union=mv_union,
                        core0_MV_idle_including_Task_gates=expected - mv_union)
        compare = {key: computed[key] == diagnosis[name][key] for key in computed}
        if not all(compare.values()):
            raise ValueError(f"{name}: interval arithmetic differs from archived diagnosis: {compare}")
        rows[name] = dict(trace_sha256=hashlib.sha256(raw).hexdigest(),
                          makespan=expected, audit_status=audit["status"],
                          hidden_slack=audit["max_operation_start_slack"],
                          critical_decomposition=audit["decomposition"],
                          computed=computed, matches_archived_diagnosis=compare)
    result = dict(kind="READ_ONLY_ARCHIVED_TRACE_INTERVAL_AUDIT_NOT_E0",
                  paired_signatures_sha256=EXPECTED_PAIRED_SHA,
                  diagnosis_sha256=hashlib.sha256(diagnosis_raw).hexdigest(),
                  rows=rows,
                  limitation="Observed-duration DAG and interval equality do not validate fair DDR service or establish counterfactual causality",
                  calls=dict(Task_compile=0, response_simulate=0, E0=0, E1=0, E2=0))
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
