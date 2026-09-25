# Local three-cell qualification handoff

This local route uses the existing Python 3.12 environment and verified Mac
native E2 export. `local-manifest.json` pins source commit
`15d86e13b4a8abb4bce445ac241aecac13f553bf`, 77 tracked source/official
files, all 51 E2 export files including the ARM64 library, config, three raw
graphs, interpreter binary and the runner. It was built read-only from the
existing worktrees. The earlier `qualification-source.zip` is a separate Linux
preparation artifact and is not the local execution entrypoint.

Only after the total coordinator admits this specific batch, write a T0 gate
JSON at a fresh path. Its exact object must be:

```json
{"status":"admitted","scope":"local-three-cell-qualification","source_commit":"15d86e13b4a8abb4bce445ac241aecac13f553bf","manifest_sha256":"a7b4e9b02c781610e9920b3856d187ca2196e1cb93db32e46040302baaf53a39"}
```

Run once from `/Users/nikolastar/.codex/worktrees/q2-continuation-s7d28/huaweicup2026`:

```sh
set -e
/Users/nikolastar/.codex/worktrees/p2-gap500-s59ee-20260925/huaweicup2026/.venv/bin/python -B output/bidirectional-qualification-20260925/local_qualification_runner.py --t0-gate /absolute/path/to/admitted-t0.json --output /absolute/fresh/path/for/three-cell-results
```

The output path must not exist. No gate was created during preparation. The
runner checks source, inputs, E2 native export and the frozen CLI's
`check_e2_source` before the first solver. It reserves up to three sequential
solver starts, 12 E2 API starts, three external E0 starts, one worker, 60
seconds per solver, 30 seconds per external E0, 300 seconds including the
preflight and all cells, and 512 MiB observer-inclusive RSS. The public E2 API
can internally use E0 fallback; one such possible call is reserved for honest
accounting. The target is zero. On the first fallback, unknown request, failed
solver or missing evidence, stop without retry or later cells. A missing or
unreadable solver ledger leaves E2/fallback counts explicitly unknown.

For each completed cell the runner retains the entire solver evidence tree,
canonical preselection candidate JSON files, each E2 request and native record,
final plan, external E0 result/trace/log, per-process wall and RSS receipts,
and a cumulative ledger. It matches the canonical final plan to exactly one
oracle attempt and compares native and external E0 Makespan plus all five
movement byte fields. A mismatch stops the batch. These checks are specified
and syntactically tested offline; no actual three-cell result has been accepted.
