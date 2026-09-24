# P2 adaptive_budget: complete 100 × 1–5 core benchmark

One fixed solver source, `2794ceba93acc1f7fc119154f61082511843d4b3`,
ran every official P2 case at 1–5 cores through
`src.q2_nikolastarx.adaptive_budget`. Four disjoint one-worker shards covered
cases 001–025, 026–050, 051–075 and 076–100, each at all five core counts.
The runner was fixed at `7483614f356099a2a8c89967241b8e9ebdb77c08`;
the four shards completed 500/500 solver calls and 500/500 separate final
unmodified official P2 E0 calls. There were no online evaluator calls or
retries. The earlier 044/k4 development probe was **not** used to fill this
full run. The concurrent batch took 517.437 s of shared-host wall time.

The [standard board feed](../../../results/a/q2-nikolastarx/active-core-full500-20260925-s59/20260924T1910Z-s59ee/board-feed-500-with-runtime-notes.json)
has SHA-256 `0b850686966d1d7c1ce1a8babb1655051756b42f9a59d5c6f6becd6a87f2f99c`.
It binds each plan, independent E0 result, run receipt and manifest to their
original file hashes and the matching official one-core baseline. Protocol
submission validation reports 500 records and 500 eligible cells. The
unsubmitted provisional feed without interpreter clarification is retained
locally but is not the publication source.

| Cores | Mean per-case official baseline speedup | Better / equal / worse than fixed ee1 frontier batch |
| --- | ---: | ---: |
| 1 | 1.108597× | 0 / 100 / 0 |
| 2 | 2.050483× | 10 / 82 / 8 |
| 3 | 2.815665× | 16 / 76 / 8 |
| 4 | 3.476781× | 21 / 71 / 8 |
| 5 | 4.014094× | 24 / 66 / 10 |

This version improves the arithmetic mean at 2–5 cores versus fixed ee1,
including 5-core 4.014094× versus 3.768826×, while losing some paired cases.
It is one complete candidate, not a splice of its winning cells with another
version. The controller/matrix runner reported Python 3.14.5; the recorded
solver and final E0 argv used `.venv/bin/python`, verified as Python 3.12.13
from `uv sync --locked`. Those interpreter roles are distinguished in the
feed notes. Per-cell solver wall remains a concurrent shared-host observation,
not an isolated throughput speedup.
