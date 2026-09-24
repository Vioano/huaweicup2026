# E2 comparison-domain check

This batch verifies E2 on six **existing fixed complete plans**, paired against
immutable E0 results. It constructs no plans, runs no new truth E0, and does not
produce an algorithm leaderboard score. The three mechanisms are deliberately
different: 012/k4 regresses without spill, 056/k5 improves despite more transfer,
and 031/k4 regresses with more spill. These cases have already been inspected;
they are not an unseen test set or a general E2 correctness proof.

`manifest.json` pins each graph, plan, E0 result, source feed, configuration,
50 evaluator source files, and the separately verified ARM64 native library.
The E2 owner confirmed source `603b0741e21c449d3db652ebd67c94f2dc014cc9` and the
library identity in [the handoff](https://github.com/huaweibei123/huaweicup2026/pull/46#issuecomment-5820487418).
Old data is at `571536962b3f6ad9468584a0e5ae04398e684543`; new data is at
`d50f48280d236c351e9cb8e75ae5a3a006cf6c89`. Historical case results are used
**only for validation**, never to choose a new solver's output.

## Reproduction

Use the committed repository and an environment prepared with `uv sync --locked`.
The native library is a macOS ARM64 build. Other platforms require a separately
verified build and a new manifest; silently substituting another binary is not
supported. No compiled binary or staged third-party source is committed here.

From the repository root, supply the existing verified binary path explicitly:

```sh
python -B src/q2_nikolastarx/e2_plan_pairs.py prepare \
  --manifest results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json \
  --e2-root output/q2-e2-plan-pairs-runtime \
  --binary-source "$P2_VERIFIED_E2_BINARY"
```

The destination must be new. Preparation reads Git objects and copies bytes;
it does not import or run E2. It exports 51 files, 482517 bytes, including the
verified binary. Reusing an existing prepared root for preflight is allowed.
Set `P2_PAIR_RUNNER_SHA` to the full commit containing the runner, manifest and
`evaluate_feedback.py` process monitor. Then:

```sh
python -B src/q2_nikolastarx/e2_plan_pairs.py preflight \
  --manifest results/a/q2-nikolastarx/e2-plan-pairs-20260925/manifest.json \
  --e2-root output/q2-e2-plan-pairs-runtime \
  --runner-commit "$P2_PAIR_RUNNER_SHA"
```

Only in the coordinated resource window, replace `preflight` with `run` and add
`--output results/a/q2-nikolastarx/e2-plan-pairs-20260925/run`. The output must
not exist. Each pair runs in a fresh subprocess, sequentially, with a 120-second
deadline; the whole batch has 300 seconds and a sampled process-tree RSS limit
of 4 GiB. No retries or resume are supported.

## Acceptance and accounting

Maximum six public E2 API requests. This E2 API has automatic E0 fallback and
no supported native-only switch, so up to six fallback E0 attempts are reserved.
Stop at the first fallback, mismatch, or failure. An interrupted in-flight
request is marked unknown; it must not be counted as zero fallback calls.

For every plan require native route, successful P2 status, exact Makespan,
all five `data_movement_bytes` fields, and `cross_task_traffic` equal to its
existing E0 truth. The pair's lexicographic (Makespan, added DDR) ranking must
also agree. Preserve the full native records, preparation/replay timing,
process receipts, runtime identity, and actual API/fallback counts.

This is a correctness-domain sample, not an E2 speed benchmark. Different
plans require fresh preparation; the second plan reuses the graph instance.
The probe's wall time includes identity checks and artifact reads and is not
solver end-to-end latency. Any subsequent online comparison must separately
include E2 initialization, preparation and scoring in the solver ledger.

## Executed sample

Completed on 2026-09-24 at 20:13:12 UTC after the production owner explicitly
released the scoring window. Frozen runner:
`b868b021b3d5fe9051613d7efeaccc200e890a33`. Runtime: Python 3.12.13,
macOS ARM64. See `run/summary.json` and the per-pair process/ledger originals.

All six public API requests used native execution; zero E0 fallbacks, retries,
errors or mismatches. Makespan, all five movement fields, cross-task traffic,
and all three pair rankings matched the immutable prior E0 results exactly.

| Pair | Whole component Makespan | DAG split Makespan | Ranking |
| --- | ---: | ---: | --- |
| 012/k4 | 13,803 | 34,274 | Whole wins |
| 056/k5 | 253,392 | 165,886 | Split wins |
| 031/k4 | 419,131 | 680,364 | Whole wins |

Total probe wall time was 16.459 seconds including identity and artifact checks.
Maximum sampled child process-tree RSS was 206,012,416 bytes; maximum including
the observer was 245,710,848 bytes. All three workers exited 0 with no surviving
PIDs and no in-flight request. The scoring window was returned immediately;
no additional evaluations were launched. These observations establish this
six-plan comparison sample only, not universal E2 correctness, new solver
quality, or a controlled throughput comparison.
