# Fixed-owner reverse, three-case mechanism probe (prepared only)

This is a proposed mechanism test on 006/052/089, each K5. It is not an online solver or a full benchmark. Source commit `b03a3e1b1b51e97a772966b49a7b63668f3af9e4`; the runner verifies all 70 source Python files against the true Git commit object and the working-tree bytes. It also pins 14 official code/input/config files, the three saved incumbent plans and E0 results, helper, interpreter real binary and exact venv invocation path. The saved incumbent is not recomputed.

After an external coordinator writes an admitted gate with exact hashes, absolute output directory, and future expiry, the command is:

```sh
/Users/nikolastar/.codex/worktrees/p2-gap500-s59ee-20260925/huaweicup2026/.venv/bin/python -B output/fixed-owner-three-preparation-20260925/run.py \
  --raw /Users/nikolastar/.codex/worktrees/q2-feedback-s8ee/huaweicup2026/data/raw/a/official \
  --python /Users/nikolastar/.codex/worktrees/p2-gap500-s59ee-20260925/huaweicup2026/.venv/bin/python \
  --gate output/fixed-owner-three-preparation-20260925/admitted-gate.json \
  --output /Users/nikolastar/.codex/worktrees/q2-continuation-s7d28/huaweicup2026/output/fixed-owner-three-run-20260925
```

The output must not exist beforehand. The command is **not admitted now**. `gate-template.json` is pending/expired by design. Bounds: 3 trace-free constructions, at most 3 independent E0, zero E2/fallback/retry, one child at a time, 30 seconds and 512 MiB observer-inclusive RSS per child, 180 seconds from preflight start, normal VM pressure, at most 256 MiB swap growth, and 10 GiB free disk. Host pressure/swap/disk is checked at dispatch, during the fixed monitor's process samples (at most 0.5 seconds between host checks), and after each child. A child/process/identity/host failure stops the batch; old originals are never overwritten.

`ledger.json` records each call before start, process receipts, source hashes, new plan and result hashes, fixed owner/partition equality, old/new Makespan, all DDR fields, and spill. Byte invariance is asserted only as an observed comparison when both actual spill byte counts are zero. Equal plans are skipped without E0. A structural constructor rejection is recorded as a stopped cell with no E0 and stops subsequent cells; it is not silently converted into a scored plan. This does not prove the retiming improves quality or speed; no real graph construction or E0 was run while preparing the package.

Offline test: `.../.venv/bin/python -B output/fixed-owner-three-preparation-20260925/offline-test.py`. A separate real venv child imported the official config parsers and fixed-owner module without reading graphs. It verifies pins and seven negative gate variants without invoking solver/evaluator.
