# P3 final-round method and evidence handoff (2026-09-26)

**Status:** method draft for the frozen fifth-core selector. This is not a final 500-cell result or a claim that the K5 target was met. The final full-500 run is in progress elsewhere; add its outcomes only after the original artifacts and fixed-version audit are complete. This note did not read active cells or run E0, E1, E2, a solver, or Pro.

## Method text for the paper

For each input graph and core count, the solver constructs a fresh Forest-policy incumbent and scores its structurally selected plans with the official P3 evaluator. Its earlier candidates include the existing pipeline and attention-witness policies; the Forest memory-order candidate applies only when its structural preconditions hold. The Forest stage uses at most three online P3 calls and selects a plan only on a strict reduction in official P3 Makespan. A certified candidate-specific lower bound can discard a proposal that cannot strictly improve the incumbent. This bound is a pruning certificate for that proposal, not a global optimum certificate.

Only at **K=5**, the final selector attempts one additional deterministic plan. It recognizes layered attention rows and their persistent tracks, requires exactly four tracks and a nonempty shared residual, and assigns each private track to its own core. All ancestor-closed shared components go to the fifth core; components with private consumers are ordered before terminal components, then by consumer phase and operation ID. A priority-based topological construction forms the per-core words. A bucket-frontier L1/UB capacity certificate and a remote-edge path guard must pass. These static checks screen a candidate; they do not replace the official evaluator's legality, memory, or timing result. The temporary component phases control construction order and add no submitted dependency or global barrier. The output has exactly `node_to_subgraph` and `core_schedules`.

The fifth-core candidate is skipped on unsupported structure, failed guards, byte-identical duplication, or a certified lower bound at least as large as the incumbent P3 Makespan. If officially scored, it must strictly reduce P3 Makespan before the solver requests **both** P2 results on the exact incumbent and proposal plans. Let `M3_old`, `M3_new` be their Cache-enabled P3 Makespans and `M2_old`, `M2_new` their no-L2 P2 Makespans, all positive integer cycles. The proposal is accepted exactly when

```
M3_new < M3_old
M2_new <= M2_old
M2_new * M3_old >= M2_old * M3_new
```

The last comparison is exact integer cross multiplication for `G_new=M2_new/M3_new >= G_old=M2_old/M3_old`. It is a **selector policy** that protects both absolute no-L2 runtime and the relative same-plan Cache benefit; it is not an extra official constraint or an objective that supersedes P3 Makespan. If a condition fails, the freshly scored Forest incumbent remains the output. A P3 evaluation rejection also retains that incumbent; unexpected exceptions fail the run and must remain visible in the receipt.

## Bounded work and complexity statement

The fifth-core branch constructs **one** proposal; it does not enumerate alternative fifth-core placements or rerank an unbounded candidate pool. The entire K5 selector allows at most three Forest P3 calls, one proposal P3 call, and two conditional P2 calls: at most **six online official E0 calls** (four P3, two P2). K1–K4 use the Forest policy, at most three P3 calls and no paired P2 calls. Unsupported, duplicate, and bound-pruned proposals consume no additional E0 call. The implementation reserves each call in a durable ledger before dispatch, including calls that fail.

Recognition, graph decomposition, component assignment, memory/frontier checks, and path checks operate on the input graph and the single constructed word. Priority ordering scans the ready set at each scheduling step, so a conservative upper description for that pass is quadratic in compute operations, apart from adjacency work and sorting; do not quote a tight whole-solver asymptotic bound without auditing all called constructors and official evaluator internals. The online official evaluations and preparation can dominate elapsed time. The call cap alone does not prove the method avoids brute-force search: its rationale is the graph-specific four-track/shared-component decomposition and one guarded direct construction. Report the **outer subprocess wall from input read through legal output publication**, including construction, all online E0 calls, selection, and finalization, separately from external final re-evaluation wall and from simulated Makespan cycles. Record cold/warm cache state and host contention; a fresh process by itself does not prove a cold OS cache or exclusive-host speed.

## Existing evidence and honest negative result

The prior fixed Forest500 baseline reports K5 mean speedup `mean(B_i/M3_i)=4.7576166788448955` across its 100 cases and mean same-plan `G_i=M2_i/M3_i=1.082917172693062`. These are **separate arithmetic means**, not a ratio of totals. The 068/K5 one-shot diagnostic used exact saved old-control and candidate plans and the official P3/P2 evaluators:

| 068/K5 plan | P3 with Cache, cycles | P2 without Cache, cycles | Same-plan G | Added DDR copy, bytes | P3 byte hit rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Forest500 old control | 116,345 | 131,631 | 1.131385 | 4,341,362 | 0.213397 |
| Fifth-core diagnostic proposal | 97,971 | 98,913 | 1.009615 | 2,564,562 | 0.050489 |

The proposal reduces absolute P3 Makespan by 18,374 cycles and P2 Makespan by 32,718 cycles, but its relative Cache benefit falls. The exact G comparison fails: `98,913 × 116,345 < 131,631 × 97,971`. Therefore this proposed plan is **rejected by the frozen joint gate**, despite the absolute improvement. This demonstrates a tradeoff in one graph, not a final algorithm gain or loss. The lower hit rate does not imply worse absolute P3 time here; Cache ratio, hit rate, DDR traffic, and Makespan describe different quantities. The 41.47-second diagnostic wall is not a solver time; the diagnostic records `solver_wall_seconds=null`. Do not splice its P3 result into the Forest500 mean or report it as the fifth-core selector's 068 output.

Sources: `src/q3/fifth_core_final_solve.py`, `src/q3/fifth_core_contiguous.py`, `src/q3/forest_solve.py`; `results/a/q3-nikolastarx/r9f-one-shot-20260926/RUN_REPORT.md` and its hashed originals; `results/a/q3-nikolastarx/forest-cachepair-delta-20260925/independent-audit.json`; `results/a/q3-nikolastarx/forest-full500-feedback-20260925/independent-audit.json`. The full-run proposal and its identity, manifest, budget, and audit conditions are in `results/a/q3-nikolastarx/r9f-final-full500-20260926/README.md`. The source reviewed for this note was worktree HEAD `65c07e062ed9be78dda32ef4bb58a9891f373de9`; the final result must cite its **actual frozen solver and runner commits**, which may differ from this readback or earlier proposed manifest identities.

## Fill only after final full-500 audit

1. **Identity and coverage:** `[solver SHA]`, `[runner SHA]`, `[official evaluator/config/input hashes]`, `[manifest/run ID]`; all 100 cases × K1–K5, completed/failed/timed out/unrun cell counts, and proof the same frozen selector and rule generated each successful plan. Keep every missing cell visible.
2. **Quality:** official P3 Makespan and single-core baseline for every cell; arithmetic mean `B_i/M3_i` by K, with K5 comparison to the Forest500 baseline. For P3, report same-plan P2 comparison at matching K and Cache byte hit rate, added DDR bytes, and any accepted/rejected fifth-core counts. Do not combine historical best cells into a fixed-version score. If fewer than 100 valid K5 cells remain, label any mean a partial preview, not full-target attainment.
3. **Selection audit:** for each K5 cell, record unsupported/duplicate/pruned/P3-not-better/paired-gate-rejected/accepted status, all scored plan and result hashes, E0 phase ledger, positive integer M values, and exact gate readback. New and legitimately reused P2 originals require exact plan-byte, graph, config, core, and evaluator identity matches.
4. **Efficiency:** per-cell end-to-end solver wall distribution (median and tail), online E0 wall and calls, outer batch wall, resource/concurrency/cache conditions, cold-start evidence if claimed, and any failed or exhausted budget. Compare solution quality and wall time as separate axes. The paper should not infer a true-device performance result from simulation.
5. **Conclusion wording:** `[After audit: fixed-version result with uncertainty/coverage limits.]` If the joint gate prevents the fifth-core candidate from changing many cells, say so plainly. If K5 mean remains below five or the new fixed version does not improve the Forest500 mean, report that negative result and retain the causal 068 mechanism observation as a diagnostic, not as a substituted score.
