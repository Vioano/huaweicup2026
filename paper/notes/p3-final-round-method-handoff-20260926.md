# P3 final-round method and evidence handoff (2026-09-26)

**Status:** final method handoff after the offline audited 500-cell export. The fixed fifth-core selector completed all cells but selected exactly the same output plan bytes as Forest500 in every cell; it supplies a negative ablation result, not an improved main algorithm. This note reads completed export artifacts and did not launch E0, E1, E2, a solver, or Pro.

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

Sources: `src/q3/fifth_core_final_solve.py`, `src/q3/fifth_core_contiguous.py`, `src/q3/forest_solve.py`; `results/a/q3-nikolastarx/r9f-one-shot-20260926/RUN_REPORT.md` and its hashed originals; `results/a/q3-nikolastarx/forest-cachepair-delta-20260925/independent-audit.json`; `results/a/q3-nikolastarx/forest-full500-feedback-20260925/independent-audit.json`. The final audited export is `results/a/q3-nikolastarx/r9f-final-full500-20260926/final-export-20260926/{summary.json,comparison.csv}`. Its fixed solver is `f6fd8153375a7fb64f9af2c8f36c35356fb7d878`; the runner is `65c07e062ed9be78dda32ef4bb58a9891f373de9`. The two original run segments, their hashes, and their distinct T0/T1 budget records remain in `summary.json`; the export combines their disjoint cell evidence without inventing a single uninterrupted run.

## Final fixed-version result and paper conclusion

The final offline export covers exactly 100 graphs × K1–K5: **500 completed, zero failed, timed out, or retried**. There were 500 fresh solver processes and 982 online official E0 calls, with no E1/E2 calls. The first preserved segment covers 400 cells and 788 E0 calls; the separate completion segment covers 100 cells and 194 E0 calls. The export itself made zero new evaluations. The same frozen solver and runner identities apply to both segments; no historical best-cell winners were assembled into this result.

Every one of the 500 selected output plans is byte-identical to the corresponding Forest control. Thus every official output Makespan, same-plan G, and output-derived traffic metric is unchanged; this fixed version gives **zero solution-quality gain**. Its K5 arithmetic mean single-core speedup remains **4.7576166788448955**, below five; mean same-plan G remains **1.082917172693062**. Mean K5 byte Cache hit rate is **31.3633318594%**. These are distinct measures and arithmetic means over the 100 K5 cells, not ratios of aggregate totals.

At K5 the fifth-core policy records **96 unsupported**, **one bound-pruned** (035), and **three paired-gate-rejected** cases (064, 068, 088); there are zero accepted fifth-core plans. The three rejected candidates must not be described as unable to improve absolute Makespan. The saved 068/K5 diagnostic proves that a fifth-core plan can improve both absolute P3 and P2 Makespans while failing the exact joint G condition. The final paper should say that the frozen **combined selection rule** did not improve the output, and cite each paired candidate's original P3/P2 artifacts before making any per-case claim about its mechanism.

Across 500 fresh child processes, summed solver wall is **1601.3245 s** (mean **3.202649 s/cell**); median is **1.157935 s**, p95 **15.235049 s**, and maximum **36.896687 s**. These per-cell walls include online construction and evaluations. Shared-host contention and OS page-cache state were uncontrolled, so these numbers do not support a speedup ratio against the earlier four-worker Forest batch. Simulated Makespan is in cycles and must stay separate from solver wall seconds.

**Recommended paper role:** retain the previously validated fixed Forest solver `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1` as the main algorithm; present the fifth-core selector `f6fd815…` as a frozen negative ablation and the 068 one-shot as a mechanism diagnostic. The extra online evaluations for this selector yielded no accepted plan; do not market those calls as an improvement. The conclusion is limited to the fixed rule and supplied 100 graphs under the official configuration, not the optimality or impossibility of fifth-core sharing in general. The simulation does not establish real-device benefit.
