# P2 shared-stationary 044/K5: official one-cell negative result

The fixed capsule from commit `65e677cd398f95bb1b273ca5a958c108ab833a05` ran once in a standard Colab CPU session on 2026-09-25 17:57 UTC. The saved [original result ZIP](run/colab-results.zip) has SHA-256 `07352ae48b55d5a8e3bafc5f6e9d32bcb7fcf2b17135a8c862a4c33ce36c7d30`. Run `python3 -B results/a/q2-nikolastarx/shared-stationary-044-pilot-20260926/audit_result.py` from the repository root for the hash, call-ledger and result checks; its generated [audit](audit.json) is saved here. No evaluator is called by that audit.

| 044, 5 cores | Previous fixed algorithm `c66559a6` | New stationary-wave constructor `65b70e29` |
| --- | ---: | ---: |
| Official P2 E0 Makespan, cycles (primary) | 43,795 | **72,955** |
| Official added COPY bytes (secondary) | 930,400 | **188,672** |
| Official spill-added bytes | not established here | 0 |

The new plan lowers added COPY by 741,728 B (79.7%) but raises Makespan by 29,160 cycles (66.6%). It is therefore **not a better P2 candidate** for this cell. The static transfer estimate happened to match the official byte count; that does not make the estimate an official time predictor. This pilot must not be promoted to a full-500 score or entered as a winner.

The new official trace reports five tasks, one on each core, with intervals `[0,14116]`, `[13116,30584]`, `[30301,48483]`, `[47483,65170]`, `[64170,72955]`. There are 121 cross-core transfers. These intervals show little concurrent task execution; the exact cause of task grouping and serialization is being checked against the frozen evaluator source before changing the constructor. In particular, the current minimax of per-core compute work ignores the task-level critical path and synchronization cost.

The receipt records exactly one cold constructor process (0.378 s) and one unmodified official P2 E0 process (0.646 s), zero E1/E2 and zero retries. The outer observed run took 1.199 s; all three process receipts report no surviving PIDs. This Colab time is not directly comparable with the previous Mac batch. The Colab session was stopped after downloading the complete result ZIP, and a subsequent `colab sessions` readback reported no active sessions. A single-cell Colab result cannot support any 100-graph average claim.
