# Prepared full 100×1–5 P2 adaptive-gap batch

**Preparation only. Scheduling release has not been granted; do not run the
solver or evaluators from this package yet.** The manifest lists cases 001–100,
each at 1–5 cores, in deterministic case-major order. Every cell uses the same
frozen `923b25ecb0b9d6d0e2d3f149fccef431b5403f99` solver entry
`src.q2_nikolastarx.adaptive_gap_guarded`, parameters, selection rules, official
graph/config/code and isolated E2 `603b074`. The `60afc38` 500-cell feed,
plans and truths are read only for identity checks and retrospective comparison;
they are never passed to the solver as a plan or score.

The runner preflights the exact 39 frozen solver `.py` files plus exactly two
auxiliary files (`gap_solver_pilot.py`, `gap_full500.py`). Both auxiliary files,
this manifest and `evaluate_feedback.py` must match the supplied full runner
commit before `run`. The on-disk `.py` set and each solver ledger's runtime
source hashes must equal that union. It also checks all 500 graph/old-plan/truth
hashes, the official source manifest/config and isolated E2 source/native binary.
The permitted read-only preparation command is:

```sh
python3 -m src.q2_nikolastarx.gap_full500 preflight \
  --manifest results/a/q2-nikolastarx/gap-full500-20260925/manifest.json \
  --e2-root output/q2-e2-paircheck-603b-s8ee
```

After separate root review and scheduling release, `run` requires
`--runner-commit <full SHA> --output <new directory>`; an existing directory is
rejected. There is no resume or retry. One monitored worker runs a fresh solver
for at most 60 seconds, including any online E2 calls, then one independent
official E0 for at most 60 seconds. Limits across the entire batch, including
preflight: 500 solver starts, 1,000 public E2 requests, 500 independent E0
starts, 1,000 reserved possible fallbacks, one worker, 7,200 seconds and 4 GiB
observed process-tree RSS. The first fallback, uncertain in-flight request,
exception, timeout, resource breach, source drift or result mismatch stops all
remaining cells. A stopped run retains its directory; another run needs a new
resource decision and new directory.

For scored plans, the first native attempt must match the frozen baseline
plan/truth. The selected online native record is found by `score_adapter`'s
canonical plan SHA and independently checked against E0 Makespan, all five
movement fields and cross-task traffic. Zero-call output must match the frozen
baseline's mapping insertion order and core schedules exactly, and its E0 must
match that old truth. A non-`UnsupportedStructure` candidate construction error
stops the run. Each cell keeps its plan, full E0 output, online ledger, source
hashes, process receipts, old/new Makespan and DDR bytes, and outer stage walls.
The summary tracks attempted/native/possible fallback calls and uncertainty.
Only 500 accepted cells can support the new full-batch mean; partial output is
explicitly incomplete and is not combined with the four-cell pilot or historical
best plans.
