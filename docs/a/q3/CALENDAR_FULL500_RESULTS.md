# P3 calendar_solve: complete 100 × 1–5 core benchmark

One fixed solver source, `8314351854c716091bc6d31215569825ae45ec55`,
ran every official P3 case at 1–5 cores through `src.q3.calendar_solve`.
The ten disjoint 50-cell shards ran from 2026-09-24 19:04:48 to 19:11:20 UTC,
with a four-cell pilot and at most eight shards active together. All 500
solver processes completed and all 500 cells have a saved winning plan and
official P3 E0 result. The solver made 861 **online** calls to the unmodified
official E0, with no E1/E2 calls or retries. The final results reuse those
online evaluations; no further independent external E0 run was made.

The [standard board feed](../../../results/a/q3-nikolastarx/calendar-full500-20260925-s59/20260924T1905Z-s59ee/board-feed-500-with-baselines.json)
contains the 500 records and 100 matched official single-core baseline
originals. Its SHA-256 is
`5e02bdb87619697130e73b62de853c0c477842972f268ef03d3818cb49bd4140`.
The as-run controller is fixed at
`3d4c79c0a4c0624db4016b3547131acca48bfdd7`; the handoff is
`e923cae8d38a351ee44290a967725046fd9d83ff`.
Fixed-commit submission validation returned 500 records and 500 eligible
cells. The feed lacking baselines is retained locally but excluded from
submission.

| Cores | Mean per-case official baseline speedup | Mean solver wall | Cells better / equal / worse than fixed expanded_solve |
| --- | ---: | ---: | ---: |
| 1 | 1.199407× | 3.795 s | 0 / 100 / 0 |
| 2 | 2.308188× | 3.962 s | 24 / 76 / 0 |
| 3 | 3.239165× | 3.816 s | 26 / 74 / 0 |
| 4 | 4.053230× | 3.957 s | 24 / 76 / 0 |
| 5 | 4.673441× | 4.355 s | 24 / 76 / 0 |

Across all 500 paired coordinates, calendar improves 98 official Makespans,
ties 402 and worsens none versus the fixed `a5dafdf...` batch. It uses more
online E0 calls (861 versus 755), and mean observed solver wall is higher at
every core count; for example, 5-core wall rises from 3.231 s to 4.355 s.
Both runs used shared-host concurrency, so their wall times are observations,
not isolated-hardware speed ratios. Keep both full candidates on the
quality–time comparison; do not splice per-cell winners or infer Cache benefit
without paired no-Cache evaluation.
