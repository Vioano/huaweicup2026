# P2 stationary job pipeline: official 044/K5 mechanism result

The fixed capsule from commit `1e9188e41ca54ef3baa3c265d14fb0d2f99c7b3c` ran **once** in a standard Colab CPU session on 2026-09-25 18:22 UTC. The complete [original output ZIP](run/colab-results.zip) has SHA-256 `c639330713bf80f4b1eee639c1aef1879bbc764e212a890aa387740edd7633b7`. Run `python3 -B results/a/q2-nikolastarx/shared-stationary-pipeline-044-pilot-20260926/audit_result.py` from the repository root to check hashes, call counts, provenance, and metrics without invoking any evaluator; its generated [audit](audit.json) is saved here.

| 044, 5 cores | c665 fixed full500 algorithm | Earlier stage-major one-cell pilot | New job-major one-cell pilot |
| --- | ---: | ---: | ---: |
| Official P2 E0 Makespan, cycles (primary) | 43,795 | 72,955 | **39,681** |
| Official added COPY bytes (secondary) | 930,400 | 188,672 | **129,536** |
| Official spill-added bytes | not checked here | 0 | **0** |

Relative to the c665 same-cell control, the new plan reduces Makespan by 4,114 cycles (9.39%) and added COPY by 800,864 B (86.08%). It is a real **single-cell** quality improvement. It does not change the official same-algorithm full500 score: the production solver has not selected or scored this candidate in a new fixed full run. Under the artificial assumption that the other 99 K5 plans remain byte-identical, this cell alone would add only 0.003655 to the 100-case mean speedup; that is a scope calculation, not a measured new full-set result. A read-only K5 structure scan found that the strict recognizer plus capacity screen accepts only 004, 044 and 093 among 100 official graphs.

The official timelines support the proposed mechanism. The [earlier stage-major pilot](../shared-stationary-044-pilot-20260926/RESULTS.md) had one task per core starting at 0, 13,116, 30,301, 47,483 and 64,170 cycles, with little overlap. The new core task intervals are `[0,29349]`, `[3209,30911]`, `[9250,32059]`, `[15020,35487]`, `[20377,39681]`: all five overlap for a substantial span. The official simulator still has one Task per core; changing `core_schedules` changed operation priority and made individual job outputs available earlier. This observed overlap supports the explanation, but it is not a general performance theorem.

The frozen runner records exactly one cold constructor process (0.211 s) and one unmodified official P2 E0 process (0.320 s), zero E1/E2 and zero retries. The outer observed process ran 0.617 s. All three process receipts have empty surviving-PID lists. The Colab session was stopped after downloading the result; `colab sessions` then returned no active sessions. Colab timing cannot be compared directly with the c665 Mac batch. Do not submit the 044 plan as a per-case offline winner, or infer success on unseen graphs from this pilot.
