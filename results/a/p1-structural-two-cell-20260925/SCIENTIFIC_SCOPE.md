# Fixed structural refinement transfer: 016 and 024, K5

This is preparation, not a benchmark result or a resource admission. Fixed algorithm source: `3a1b82b71ca1ff6689eb8e72f17d26c48b52073c`, entry `src/q1/structural_refine.py`. The 47 tracked files under `src/q1` and `src/eval_exact` were compared byte-for-byte with that source before preparing this run. No algorithm code is changed for these two inputs.

## Question and prior evidence

The existing strict intact fork/join candidate improved 051/K5 from the unified-v4 official Makespan 253856 to **231551**, selected `intact-root-heavy-fused`. Its official result, plan and run are in `results/a/p1-structural-runner-pilot-20260925/public/cells/051/k5/`. That result used the same fixed structural solver. It is a single-cell result, not a new unified full matrix.

016, 024 and 051 share repeated 12-branch fork/join structure; earlier static documentation reports respectively 305, 101 and 24 rounds. The proposed two cells test transfer to larger repetitions. They do not tune parameters or choose a winner from old saved plans. Each graph goes through the actual frozen unified CLI once, including candidate selection and fallback, then its emitted plan goes to E0 once.

The current full benchmark remains unified v4, source `a0537aeb72dc702af86d67d3194587d581ac207c`, run `20260924T1952Z-s59ee`, K5 mean **4.025907473836023**. Its 016/K5 and 024/K5 official Makespans are **3223183** and **1067515**. Extra DDR is **119555952** and **39327648** bytes; both have zero spill. The proposed run must report both Makespan and DDR, plus cold end-to-end solver time and external E0 time separately.

## Input identity and budget proof

Original bytes were independently read from the frozen `data/raw/a/official-cases.zip` and matched to `docs/a/source-manifest.json`:

| Graph | Bytes | SHA-256 | Compute operations |
| --- | ---: | --- | ---: |
| 016 | 6110151 | `76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef` | 17995 |
| 024 | 2014832 | `f974fbf1a23b4a145b5f8c9c691eb1b247f93d8785d98bb46a9cdd8626399aec` | 5959 |

Both compute-Pipe sets are exactly `{PIPE_V}`. In frozen `unified.generate_candidates`, `capacity-return` is attempted only if that set equals `{PIPE_M, PIPE_V}`. Thus neither input can select it. Frozen `response_refine.scored_capacity_winner` requires that selection before constructing/scoring a packet refinement. These inputs therefore invoke **zero packet-refinement children**, zero Fraction response runs, and no packet-refinement E1.

The unified parent has at most six distinct candidates; the structural wrapper adds at most two E1-scored intact candidates. This proves a conservative tightened bound of 8 E1 per cell / 16 total for these fixed inputs. The general entry may use 9 per cell, so the preparation can retain the more conservative administrative ceiling of **18 total**, while recording this stronger source-based argument. The source-level limit is separate from actual runtime dispatch counts, which must be reported (unknown on interruption must not be silently changed to zero).

Planned ceilings: solver 2, E1 at most 18, E0 at most 2, E2 and retries 0; one worker; solver 180 seconds per cell; E0 120 seconds per cell. Remote execution 540 seconds (host exec timeout at most 560 seconds); independent stop lease 690 seconds; VM overall cutoff 720 seconds. Shared resource admission and immutable package pins are required before dispatch. Stop on the first failure, timeout, unverifiable call ledger or cleanup failure, preserving unrun cells. No automatic expansion to 500 cells.

## Interpretation

A positive transfer is evidence for the candidate family, not a guarantee of improvement on other graphs or all core counts. E1-based selection does not by itself prove E0 monotonicity. Final official outputs, failure inheritance and the full same-source matrix remain necessary.

Fang's fixed R4 theory package `5c5789bc7985ee98086160f75770da0018f4898b` supplies computation-window and universal-barrier lower bounds. Its paired CSV gives K5 bounds 2033550 for 016, 672870 for 024, and 159280 for 051. These are not attainable targets or predictions. This session read the proof, audit notes, CSV and key frozen E0 integer/event/gate code; it did not independently rerun all 433 separator checks or all 500 original results.

A pure arithmetic read of that CSV also shows that a historical fewer-active-core envelope would improve the v4 K5 mean by only 0.010950870901624879 across 14 cells. This is not an implemented selector or new measurement, and alone does not justify a promise of a substantial breakthrough.

The user's stop condition is a verified significantly improved benchmark from one fixed unified algorithm, fully published and mirrored, followed by a pause pending instructions. Neither two-cell success nor hypothetical mixing of historical winners satisfies it. If this experiment is negative, retain the evidence and reassess the mechanism; do not silently add scans or declare the conditional stop achieved.

## A falsifiable transfer prediction from the saved 051 trace

Reading the existing 051 official result (no new evaluation) and matching its Task IDs to the saved constructor diagnostics shows round 0 finishing at 9762, with all 23 later round-completion differences exactly 9643 cycles. The repeated steady-stage worker Tasks finish 516 cycles before the final residual reduction may start; the foreign-core gate is visible in the saved timeline. This is an observed timing pattern, not a causal intervention or a theorem for every graph.

If the identical pattern transfers without changed FIFO, memory or numeric-event behavior, 101 rounds would predict 974062 cycles for 024 and 305 rounds would predict 2941234 cycles for 016. These are **unmeasured hypotheses**, not benchmark data, certified upper bounds or required pass values. Actual E0 decides. The two future results should retain any disagreement and its full trace; do not adjust a plan to force the prediction.
