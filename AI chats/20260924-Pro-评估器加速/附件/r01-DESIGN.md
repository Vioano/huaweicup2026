# Design and falsifiable next steps

## Decision

Priority: an exact prepared-task interpreter on compact arrays, native global replay, and an immutable partition handle. Backup: max-plus elimination of non-DDR interiors, initially only in provably DDR-empty intervals or entirely no-DDR inputs; fall back to exact replay whenever the guard cannot prove equivalent event/rounding behavior. Do not restart scalar calibration, generic Step3 memoization, compulsory GC or a full Rust rewrite.

This is not choosing between E1/E2 branding. It is choosing to remove representation, observation and repeated preparation costs before removing semantics.

## A proposed production boundary (not fully implemented here)

```
GraphHandle = prepare_graph(raw_graph, frozen_source_identity)
PartitionHandle = prepare_partition(GraphHandle, ordered_raw_mapping,
                                    exact_bandwidth, ordered_capacity)
Score = score(PartitionHandle, core_schedules, cross_wait, same_wait,
              deadline, max_iter, trace_mode=False)
```

Graph and partition handles own immutable input snapshots. Cached success must not imply a schedule has passed union-cycle validation. The stable raw official/E1 entry point remains unchanged. Errors outside the typed fast domain must be resolved by the official path; no missing score may be silently treated as a bad candidate. No whole-result cache is needed.

The implemented `pack_tasks(tasks,runtime,bandwidth)`/`score(comp,orders,...)` is a smaller, useful experiment at the prepared-task boundary. It is NOT the full production handle API.

## State invariants and the safe coalescing lemma

A compiled task has fixed data/memory predecessor arcs and a fixed order on every pipe. Each pipe has one slot. FIFO advances only when its current operation retires. At most one task per core is active. All operations last at least one cycle. Therefore an issue pass cannot itself make another operation eligible on the same pipe or satisfy a completion dependency on a different pipe. Replace a size-at-most-one issue heap by the eligible head and eliminate the redundant fixed-point pass.

Within that issue phase, DDR reprojection writes predicted ends, but those intermediate predictions do not affect readiness, FIFO head movement, membership, or the work-remaining state. Keep new-transfer insertion order, every work-update call, and the final reprojection; intermediate reproject calls may be removed when their trace snapshots are not requested. This does not permit coalescing retirement phases, merging different timestamps, changing rounding, or bypassing FIFO heads.

The native implementation retains dictionary insertion semantics with a stable active vector and separately stores the exact original `(task_id,op_id)` comparison rank. Task simultaneous completion follows the original task insertion order; retirement and issue follow core then official PIPES order. All four pipes can theoretically carry DDR COPY under the validated schema, so do not hardcode `2*cores` as the active-transfer cap.

## Backup algebraic interface

For every non-DDR fixed-duration operation, after adding FIFO edges,

    finish(v) = duration(v) + max(task_start, finish(u) for u in predecessors).

Retain DDR operation start/end ports and task start/end ports. Eliminate non-DDR interiors by max-plus longest-path lags between ports. This preserves causal transfer arrival times in real arithmetic and is fundamentally different from replacing an entire task by its isolated duration or average bandwidth.

Port-to-port edge count may grow quadratically. If ports are not much fewer than operations, preparation/edge traversal may be more costly than replay. Stop that route on such partitions. For exact binary64 replay, eliminated compute completions can be relevant because the official global loop advances DDR work at **every** event. A max-plus algebraic identity alone does not preserve those rounding cuts. `clock_cut_probe.py` proves the issue with a concrete representable witness. No general contention-aware compression is claimed. Two executed compiled-state counterexamples are now also included: an eight-operation large-work case, and an 835-operation L1-sized case (480,000 bytes < 524,288 capacity; 828 clock cuts). Their wrong compressed Makespans differ by one cycle. The proposed raw graph/plan for the latter are supplied but remain UNEXECUTED under frozen Step1–3. A one-cycle mismatch falsifies exactness; it does not by itself falsify the user's looser approximation-error gates.

The no-DDR special case is implemented and tested. For dynamically DDR-empty intervals, retain all task/release/next-DDR interface events and prove no external DDR arrival occurs inside an eliminated interval; otherwise expand/fall back. This dynamic guard and interval rounding certificates are NOT implemented in this delivery.

## Failure witnesses and required official probes

- FIFO: M=100; V queue [A=1 depending on M, B=100 independent] completes at 201, whereas bypassing A yields 101. This is a compiled-state witness, not a claim that a supplied raw Step3 run produces that queue.
- COPY/compute overlap: independent DDR10 and compute100 can finish in100, not110. Two simultaneous DDR1 transfers finish at2, not1.
- Simultaneous events: retire all scheduled finishes, then activate tasks, then issue. Do not interleave one retirement and a fresh issue unless it is proved equivalent.
- DDR zero-work entries: positive-work membership used by advancement differs from not-yet-retired membership used by projection. Preserve the distinction and `1e-9` comparisons.
- Capacity: input8 and output8, both needed at execution, require16 bytes at the alloc-before-execute boundary. Capacity8 cannot be made legal by freeing the last-use input early. With a separate spillable victim, capacity changes by one byte can insert a whole COPY/reload chain or change memory edges.
- Backing: existing DDR backing means no new spill-out; `spill_out_id=None`, just new COPY_IN. For an originally unbacked logical tensor the first real spill creates backing, which later spills reuse. `2*size` for every spill is wrong.
- Incarnations: logical identity is not physical residency identity. New COPY_IN creates a new version; all readers of the old physical version, including a real COPY_OUT, govern freeing and WAR/WAW. L1–UB COPY is not shared-DDR work simply because it is a COPY.
- API numbers: official waits may be floats although official config uses integers. The prototype guards them out. Oversized integers, float-to-int conversion, grouping near epsilon and rounding near integer boundaries require explicit adversarial tests.

Capacity/backing/incarnation correctness here is inherited only when fed authentic official prepared tasks; the synthetic runs do not test that inheritance boundary.

## Cache invalidation

A graph handle binds the graph's byte/schema identity and ordering, frozen-source identity and numeric rules. A partition handle binds ordered mapping with original numeric/key representation, capacity values/order, and exact bandwidth representation. Never replace that by just task count, tensor totals or topology without tensor attributes. Persistent native handles additionally bind ABI, compiler flags, architecture and engine version.

- graph/order/node/tensor/edge/attribute change: new graph and partition handles;
- mapping change, including conservatively raw mapping-order change: new partition handle;
- capacity or bandwidth change: recompile local Step1–3 and repack;
- core assignment/core order/core count: reuse local immutable arrays, revalidate schedule and resize/reinitialize scratch, replay global events;
- cross/same waits: reuse local arrays, replay globally; changed number types may require fallback;
- max_iter/deadline: per-request simulation/guard setting, not a cached success;
- source/compiler/ABI/numeric-policy change: invalidate affected persistent compiled handles.

Use graph/partition ownership rather than repeatedly hashing megabytes for each trusted inner-loop candidate. For raw untrusted plans retain explicit full validation or prove an equivalent staged validator. No mutable alias may leak from an output into a cached handle.

## End-to-end budget

First measure the actual sums: T_total = preparation + sum(all fast scores) + sum(exact shortlist scores) + sum(fallback evaluations) + sum(E0 audits) + initialization/IPC/scheduling. For a simplified homogeneous-cost model, let e be the measured same-machine average new-E1 cost/candidate, N=64, s the fast all-pool speed, q=e/(average exact shortlist evaluation cost), rho the E0/new-E1 cost ratio, A the number of E0 audits/confirmations, F fallback cost in units of e, H all other preparation/IPC/initialization cost.

    T / (64*e) = 1/s + 8/(64*q) + A*rho/64 + F/64 + H/(64*e)

Do not count an already-computed exact score twice. If full native all-pool scores are trusted exact under the validated domain, shortlist selection can reuse them; rendering trace or independent audit remains a separate charged operation. If q=1, even free all-pool screening has an end-to-end ceiling of8×. Existing-E1 shortlist evaluation implies q=1 ONLY when its average cost equals the all-pool average. For heterogeneous costs the exact screening-free bound is sum(all-pool E1 times)/sum(shortlist E1 times), not necessarily8. This corrects the initially overbroad verbal bound. A claimed 10× scoring stage is not a claimed10× search pipeline.

For an accelerated fraction 1-f and kernel speed k,

    overall_speed <= 1 / (f + (1-f)/k).

At f>=0.1 the 10× target has no headroom even with a free kernel. Cold partition compilation repeated once per K schedules costs C_compile/K per candidate; measured K=1/8/64 and changing-partition mixes are essential. Do not amortize it over a fictitious huge search.

Search objective: distinct, validated candidate count and best E0-confirmed solution at fixed wall time / total CPU seconds / RAM, including algorithm candidate generation, compilation, transfer, shortlist, fallback and audit. Paired search seeds and family-diverse proposals are required to avoid optimizing only evaluator microbenchmarks.

## Resources and parallelism

Use bounded work-conserving dispatch and partition affinity; do not wait for every candidate in a worker-sized chunk before feeding the next idle worker. Preserve reproducibility by candidate ID and deterministic application of results, not by uncontrolled completion order changing the search. A bounded resequencing window may be needed for deterministic adaptive search. Track its utilization cost.

Compiler preparation may be a separate budgeted process that emits read-only compact arrays; workers need not all retain raw graphs and official task dictionaries. Shared read-only data and per-worker mutable scratch should be explicit. Cache-byte caps are not RSS caps. Compare the same allowed CPU and total RAM budget for every design; count the compiler and parent, not only replay workers. Threads require independent scratch/immutable data, and hard per-candidate termination is easier with process isolation. No thread scaling or long-run RSS guarantee has been demonstrated here.

The delivered resource test includes expensive monitoring and Python imports. It demonstrates that 50×-scale resident replay can still have only 2–3× cold-pool speedup. The sampled tree RSS sum double-counts shared pages; it is not a physical peak/PSS measurement or an OS-enforced bound. The small compiled fixtures do not demonstrate memory savings on the user's case003.

## Staged gates and stopping rules

1. Profile the actual new E1, on same machine/config/candidates: immutable graph validation, partition derivation, key encoding, decode/set rebuild, global replay, DDR math, trace construction, parent/child transport. Obtain a cost fraction, not speculative percentages.
2. Use the delivered prepared-task native probe on official002/003/008 with at most3 new schedules each. Any integer timestamp, status or debug projection difference stops the exact claim; preserve the failing input and source identity. Existing capacity/backing/incarnation tests are mandatory next.
3. Independently ablate compact representation, graph/partition handles, log/output elision, native port and same-phase coalescing. Preserve reference sources. Balanced timing order and repeat-from-cold epochs; record initialization and compilation separately.
4. If the remaining unaccelerated cost makes10× impossible, do not scale a benchmark or train a model to hide it. Fix the handle/validation/preparation boundary or stop the10× claim. Use the algebraic backup only on partitions where interface count, guarded compression and preparation amortization justify it.
5. Run multiple independent official graph/algorithm-family pools, each64 unique valid candidates with all64 truth values. Old dev64 is development data, not holdout. Select top8 with declared tie-breaking. Report per-graph and pooled median/P95/max error, worst-pool regret, failures, every omitted good candidate, avoidable shortlist loss, and all fallback costs.
6. Success set G = {i: M_i <= 1.01*min M}. Report pool hit iff shortlist intersects G. Also report |G outside shortlist| and max(0,min(8,|G|)-|G intersect shortlist|) to separate unavoidable top8 truncation from avoidable loss.
7. Four passing synthetic pools do not establish95% reliability. If independent identically distributed pools all pass,59 zero-failure pools give a one-sided95% binomial lower bound above.95 (`0.05**(1/59)`); pools sharing graph/algorithm history may be correlated, so graph-level holdout and clustered uncertainty still matter. This is a statistical design criterion, not a promise of universal correctness.
8. Finally run fixed-budget adaptive searches, 1/2/... workers within the same machine resources, cold/warm/mixed partition regimes, saturation and multi-hour RSS/recycling tests. Charge exact/E0 audits and fallback to the search budget. A release passes only the user's unchanged joint thresholds, not just a low average error or a fast kernel.
