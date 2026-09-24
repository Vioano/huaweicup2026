# P1 unified v4: complete 100 × 1–5 core benchmark

One fixed solver source, `a0537aeb72dc702af86d67d3194587d581ac207c`,
ran each of the 100 official P1 graphs at 1–5 cores through
`src/q1/unified.py`. The independent batch used runner/manifest
`85b99a74101e3a7981b60566ad7937bcc8dc5426` and run ID
`20260924T1952Z-s59ee`. It completed 500/500 fresh solver calls and
500/500 separate unmodified official P1 E0 calls; the solver made 1,028
online E1 calls. There were no E2 calls, retries, baseline reruns, or reused
cells from the earlier stopped window or isolated diagnostic. All process
groups were cleaned up. Shared-host batch wall time was 1,049.256 s with at
most four concurrent workers, each guarded by a sampled 4 GiB group RSS
tripwire. The fixed solver/E0/batch wall caps were 300/900/4,500 s.

The [standard board feed](../../results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json)
has SHA-256 `4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764`.
It includes the 100 existing, matched official single-core baseline originals
from commit `6fcec11ccc472a1a652b21feb6fccf85a4555598`. The exporter
checks original file hashes, E1/E0 consistency, result identity, and process
cleanup. Its derived public receipts redact local paths and leave overlapping
concurrent `RUSAGE_CHILDREN` CPU fields null; per-process wall times remain.
Protocol admission is a separate check from actual solver/evaluator execution
and from central site acceptance.

| Cores | Mean of 100 per-case baseline / official E0 Makespan | Better / equal / worse than fixed v1 full batch | Mean solver wall | Mean separate E0 wall |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1.002097× | 0 / 100 / 0 | 0.293 s | 4.527 s |
| 2 | 1.947513× | 14 / 86 / 0 | 3.279 s | 3.813 s |
| 3 | 2.739047× | 13 / 87 / 0 | 3.414 s | 4.427 s |
| 4 | 3.453040× | 12 / 88 / 0 | 3.411 s | 8.705 s |
| 5 | 4.025907× | 10 / 90 / 0 | 3.441 s | 5.718 s |

The largest external E0 wall was 462.655 s, for case 014 at 4 cores;
its new-run Makespan was 4,500,863 cycles. The earlier independent batch
stopped at that coordinate under a 180 s E0 cap after 149 valid cells, and a
separate one-cell diagnostic finished in 378.595 s. Both remain historical
experiments; neither contributes to this 500-cell score. The 5-core gain over
v1 is small, so retain both complete candidates when comparing solution
quality against measured solver time. At 5 cores, added DDR-copy bytes rise
for 7 cases, fall for 4, and tie for 89 versus v1; the Makespan result does
not imply improvement on every secondary metric. Shared-host concurrent
timings are not isolated-hardware speed ratios.
