# Static mandatory DDR audit

This is a zero-evaluator mechanism audit of six fixed plans, not a solver performance batch. `audit_pairs.py` loads the pinned plans and existing E0 results from the six-plan integration manifest, verifies their hashes, and counts mandatory COPYs from original tensor/core incidences. All six byte totals equal existing E0 `scheduled_copy_bytes - spill_added_copy_bytes`; cross-transfer counts also agree. Service work remains a model lower bound with the numeric limitations documented in `candidate_ddr.py`.

| Plan pair | Whole mandatory work | Cut mandatory work | Existing whole Makespan | Cut rejected by absolute work? |
| --- | ---: | ---: | ---: | --- |
| 012 / 4 cores | 9,888 | 32,389 | 13,803 | Yes |
| 056 / 5 cores | 3,872 | 130,473 | 253,392 | No |
| 031 / 4 cores | 109,460 | 351,187 | 419,131 | No |

Units are cycles in the integer DDR service model. The 056 cut previously improved E0 Makespan, while the 031 cut regressed with extra spill; the bound alone distinguishes neither outcome. Passing this filter is not proof of improvement. This initial counter audit preceded its integration into the experimental guarded solver. The production `adaptive_budget` is unchanged, and these results do not change any published algorithm score.

Run with the locked environment from the repository root:

```sh
.venv/bin/python -B -m unittest tests.test_q2_candidate_ddr
.venv/bin/python -B results/a/q2-nikolastarx/mandatory-ddr-20260925/audit_pairs.py
```

Six focused synthetic tests compare COPY insertion with the frozen official builder while scheduling, spilling and preparation are replaced by stubs. They cover per-core input reuse, multiple source/destination cores, separate output and cross transfer, terminal outputs, zero-byte direct edges, and rejected numeric inputs. Neither test command runs E0/E1/E2 or an official scheduling stage. `summary.json` contains hashes, fixed input references and counts.

## Historical rejection coverage

`audit_frontier.py` reads the fixed old `5715369` and frontier `d50f482` data and the previously audited route classifications. Its output `frontier-coverage.json` records hashes and 59 original component-DAG proposals at four/five cores. No new plans are generated and no evaluator is called.

| Cores | Historical proposals | Losing proposals rejected | Losing proposals passing | Winning proposals rejected | Winning proposals passing |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 28 | 15 | 5 | 0 | 8 |
| 5 | 31 | 17 | 5 | 0 | 9 |

All 59 task COPY byte totals match the corresponding existing E0 originals, and each calculated work is at most its own observed E0 Makespan. The screen rejects 32 of the 42 known regressions and none of the 17 known improvements. This is post-hoc mechanism coverage, not proof for unseen graphs, realized call savings of the guarded wrapper, or a best-cell portfolio score. Those remaining losses explain why complete scoring remains necessary.

The guarded hook applies the strict inequality only after a successful baseline score and the existing pipe screen. Equality and unknown counts retain complete comparison. Its counter/guard/adapter synthetic suite has 21 passing tests; actual E2-domain and solver performance validation remain separate.
