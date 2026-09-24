# Four-cell adaptive gap solver pilot

This package fixes one new solver version, `923b25ecb0b9d6d0e2d3f149fccef431b5403f99`,
and four P2 coordinates: 003/k2, 005/k3, 056/k5, 008/k5. It is a partial
mechanism test, not a same-algorithm 100×1–5-core result. The four historical
baselines are read only from the unified `60afc38` feed and its exact plan and
official result artifacts. The runner never reads their scores to choose a plan.

The runner checks all 39 frozen `src/q2_nikolastarx/*.py` solver files byte for
byte, the official source manifest and each graph/config, the isolated E2
source/native binary, and the four baseline plans and truths. `run` also
requires the runner, manifest and process monitor to match a full caller-supplied
runner commit. The read-only command below was completed with **0 scoring calls**:

```sh
python3 -m src.q2_nikolastarx.gap_solver_pilot preflight \
  --manifest results/a/q2-nikolastarx/gap-solver-pilot-20260925/manifest.json \
  --e2-root output/q2-e2-paircheck-603b-s8ee
```

The future `run` mode additionally requires `--runner-commit <full SHA>` and
`--output <new directory>`. It starts one full solver process per coordinate
with `--wall 60`; all online E2 requests and their source checks are inside
that solver wall. It then starts one independent unchanged official E0 process.
The outer monitor keeps separate process receipts, observes the process tree's
RSS, and stops and cleans descendants at the per-stage or batch deadline.

Limits are 4 solver launches, 8 public E2 requests, 8 reserved possible E0
fallbacks, 4 independent E0 runs, one worker, 60 seconds per solver, 60 seconds
per E0, 600 seconds from batch preflight start, 4 GiB observed RSS, and no
retries. A fallback, uncertain in-flight request, non-structural constructor
error, missing selected native record, process failure, or metric mismatch stops
the remaining cells. A zero-score route is accepted only when the final plan
matches the frozen baseline plan; its E0 result must then match that baseline
truth. Native selected records are located using `score_adapter`'s canonical
plan SHA and checked against independent E0 for Makespan, five movement fields,
and cross-task traffic.

The output keeps actual call counts, solver/E0 process receipts, solver source
hashes and attempt ledger, selected plan and full independent E0 result. The
first failure is preserved; no directory is overwritten or resumed. These
limits do not authorize a production run; no solver or evaluator was started
while preparing this package.
