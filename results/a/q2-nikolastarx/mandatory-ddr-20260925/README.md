# Static mandatory DDR audit

This is a zero-evaluator mechanism audit of six fixed plans, not a solver performance batch. `audit_pairs.py` loads the pinned plans and existing E0 results from the six-plan integration manifest, verifies their hashes, and counts mandatory COPYs from original tensor/core incidences. All six byte totals equal existing E0 `scheduled_copy_bytes - spill_added_copy_bytes`; cross-transfer counts also agree. Service work remains a model lower bound with the numeric limitations documented in `candidate_ddr.py`.

| Plan pair | Whole mandatory work | Cut mandatory work | Existing whole Makespan | Cut rejected by absolute work? |
| --- | ---: | ---: | ---: | --- |
| 012 / 4 cores | 9,888 | 32,389 | 13,803 | Yes |
| 056 / 5 cores | 3,872 | 130,473 | 253,392 | No |
| 031 / 4 cores | 109,460 | 351,187 | 419,131 | No |

Units are cycles in the integer DDR service model. The 056 cut previously improved E0 Makespan, while the 031 cut regressed with extra spill; the bound alone distinguishes neither outcome. Passing this filter is not proof of improvement. The static counter is not yet wired into the production `adaptive_budget` or the experimental guarded solver, and these results do not change their published performance.

Run with the locked environment from the repository root:

```sh
.venv/bin/python -B -m unittest tests.test_q2_candidate_ddr
.venv/bin/python -B results/a/q2-nikolastarx/mandatory-ddr-20260925/audit_pairs.py
```

Six focused synthetic tests compare COPY insertion with the frozen official builder while scheduling, spilling and preparation are replaced by stubs. They cover per-core input reuse, multiple source/destination cores, separate output and cross transfer, terminal outputs, zero-byte direct edges, and rejected numeric inputs. Neither test command runs E0/E1/E2 or an official scheduling stage. `summary.json` contains hashes, fixed input references and counts.
