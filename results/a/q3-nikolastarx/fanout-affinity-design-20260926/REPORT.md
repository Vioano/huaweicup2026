# P3 gap-DAG fanout affinity: static design and falsifier

## Subsequent frozen static trial

The isolated [one-shot tie-break trial](RESULTS_V2.md) tested the lowest-risk version of this idea on 010/015/065, preserving modeled finish as the primary criterion. It changed seven operations' core assignment in 015 but did not reduce modeled finish, cross-core pair count, or cross-core bytes in any of the three graphs. Therefore this **exact tie-break is not promoted to official scoring**. The accounting mismatch and broader affinity idea remain valid questions, but the trial provides no positive performance evidence. No official Task/Step/E0 was called.

## Decision

There is a real accounting gap, but not a proven score gain. `gap_dag.py` expands each original tensor into producer→consumer op edges (lines 20–32), aggregates their transfer estimates only by **chain pair** (58–67), and scores a candidate by modeled finish before a count of cross-chain predecessors (93–131). It has no state keyed by original tensor and destination core. In P3, the unmodified official builder inserts one COPY_OUT/COPY_IN pair for each distinct `(tensor, producer core, consumer core)` with different cores (`multicore_cut_evaluate_problem_3.py` lines 141–215). Thus multiple consumers of the same tensor on one remote core share one boundary pair; splitting them across remote cores adds pairs. The old delay models some transfer latency but does not compute this fanout cost or a lookahead affinity rule. This is a falsifiable mechanism direction, not a claim that the current placement is poor in official Makespan.

## Frozen provenance and scope

- Worktree HEAD: `b03fcab088322fb17a7cb5da3fb56a16802b8cc7`; `src/q3/gap_dag.py` SHA-256 `b61b1e33fcddc3491b7c37b12b41f8314d9744909957528296c0684bf57fc219`. This is the source actually read; its header attributes the constructor to Fang's fixed `a37eb931a22fb7df7e0d00d193538ce5289ae045`.
- Raw graph: `data/raw/a/official/data/case_010.json`, SHA-256 `fd0b07588473d8b2ce05fab4798808cbc7f60cf1638e05608adc3d62061b8775`.
- Saved five-core gap plan: `results/a/q3-nikolastarx/gap-probe-20260925/run/cells/010-k5-unified-general-gap-e0/evidence/gap/plan.json`, SHA-256 `4e9b1c875014bad7800596def5097ffcdcd224d5737ac2d8fdf096bc88af1a89`. It is an older saved artifact used only for placement structure. The outcome audit records 20,608 official cycles for the gap-selected fixed run, but that number is **not** an outcome of this proposed change.
- Official P3 boundary source read: `data/raw/a/official/code/multicore_cut_evaluate_problem_3.py`, SHA-256 `eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0`.
- [`FREEZE.md`](FREEZE.md) fixed the input hashes, selection rule, and stop condition before [`static_witness.py`](static_witness.py) ran. The command was `python3 results/a/q3-nikolastarx/fanout-affinity-design-20260926/static_witness.py`; it only parsed the graph and saved plan. No official E0, Task/Step, solver, Pro, or network call occurred.

## Exact incremental boundary cost

For original tensor `t` of `s_t` bytes, let `P_t(c)` and `C_t(c)` count its eligible compute producers and consumers currently assigned to core `c`. The P3 cross-core boundary pair count is exactly

`L_t = Σ_{a≠b} 1[P_t(a)>0] · 1[C_t(b)>0]`.

Its cross-core traffic field contribution is `s_t L_t`. Its inserted COPY-operation byte volume is `2 s_t L_t`, one nominal COPY_OUT and one nominal COPY_IN per pair. This does **not** equal actual DDR service, read-only cache misses, spill traffic, or simulated latency. For a proposed relocation/exchange of a small set `S` of whole chains, update counts only for their incident original tensors; the exact delta is

`ΔB = Σ_{t incident to S} s_t (L_t(after) − L_t(before))`.

Include direct op→op edges separately, one boundary pair per crossing edge, because the official builder does not coalesce them by tensor (`multicore_cut_evaluate_problem_3.py` lines 217–242). For one-producer `t` on core `p`, moving one consumer from `a` to `b` has the simple form

`ΔL_t = 1[b≠p and C_t(b)=0] − 1[a≠p and C_t(a)=1]`,

using counts **before** the move. It charges the first remote consumer on a core and credits only the last one leaving. Moving a group at once uses the general before/after formula. Input tensors with no eligible compute producer and final graph outputs require their separate original COPY accounting if a broader total-byte proxy is desired; they are excluded from the cross-core `L_t` above.

A concrete bounded change to gap placement is to maintain per-tensor producer/consumer-core counts, then score the existing `k` or `k²` calendar candidates by `(projected finish, exact incremental boundary bytes, deterministic existing tie fields)`, or apply a fixed, documented bounded slack to projected finish if transfer reduction is allowed to trade compute delay. Replacing `cuts` alone only resolves ties after the current primary finish criterion; it is a low-risk first falsification. For each candidate pair `(j, join)`, evaluate their **joint** delta before committing, then update the counts once. A later local exchange can use the same delta but must keep whole chains and rebuild/check the full schedule. The affinity signal is original-tensor core multiplicity, so it differs from the existing pairwise predecessor cut count. No arbitrary weighted total is needed.

With `k≤5`, initialize tensor counts in `O(E+kT)` time and `O(kT)` space for `T` tensors and original incidence count `E`. A tentative one- or two-chain placement touches only incident tensors and direct edges; with `k`-bit core masks, each affected tensor's `L_t` is recomputed in constant bounded time. Across at most `k²` choices per committed chain, the added work is `O(k² E)` in a straightforward implementation, beside the existing `O(E+k²N log N)` gap construction. The claim assumes incidence lists are precomputed and each chain commits once; a later iterative exchange needs its own move bound and runtime accounting.

## Real-graph local counterexample

The frozen scan selected the smallest qualifying tensor ID in `case_010`:

| Item | Static readback |
|---|---:|
| Tensor | 14, L1, 1,728 bytes |
| Unique compute producer | op 13 on core 2 |
| Compute consumers | ops 17 and 19, both on core 4 |
| Existing gap chains | producer chain 0; consumer chains 2 and 3 |
| Remote consumer edges | 2 |
| Distinct remote source→target core pairs | 1 |
| P3 cross-core traffic from this tensor | 1,728 bytes |
| Nominal inserted COPY_OUT + COPY_IN bytes | 3,456 bytes |

For this tensor alone, relocating consumer **chain 2** to core 2 would reduce remote **chain-edge count** from 2 to 1 while leaving `L_14=1` and its 1,728-byte cross-core contribution unchanged, because consumer chain 3 remains on core 4. Relocating both consumer chains to core 2 would set `L_14=0`, reducing this contribution by 1,728 bytes and removing one nominal COPY pair. These are algebraic counterfactuals, **not legal candidate plans**: other incident tensors, whole-chain ownership, per-core order, pipe contention, L1/UB capacity, and cache behavior were not recomputed. The witness proves that edge-count affinity can misrank moves; it does not prove an improvement in official Makespan.

## Safe trial gate and stop rule

First implement only the count-based tie-break in an isolated candidate source, preserving the old score as an explicit control and freezing the rule before any scoring. On the fixed `010/015/065` cohort, statically inspect whether any candidate choice actually changes; if none does, reject this simple tie-break without E0. If a changed candidate exists, require complete op coverage, valid subgraph/core order and all original dependencies via the existing plan validator, then check affected tensor-pair deltas and modeled per-pipe finish on the **whole** plan. A byte reduction is insufficient: a slower calendar finish, spill, capacity violation, or cache miss shift can reverse it. Only a separately authorized fixed-input official P3 comparison can test Makespan and DDR/cache effects. Bound its E0 calls and solver wall time in advance; retain failures. Any full-score claim requires a newly frozen single solver and 100×5 evidence. This report authorizes no such run.
