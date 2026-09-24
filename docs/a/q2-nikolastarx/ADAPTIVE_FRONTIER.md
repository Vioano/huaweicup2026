# Component balance and shared-input waves

## Complete official benchmark (2026-09-25)

The design notes below predate the benchmark. A fixed source version
`ee1b8fd39efab8c8ed8140bbebe4c08e778052b9` was subsequently run on all
100 official P2 cases at each of 1–5 cores, using entrypoint
`src.q2_nikolastarx.adaptive_frontier`. All 500 plans passed independent,
unmodified official P2 E0 evaluation; there were no online E0/E1/E2 calls or
retries. The complete [board feed](../../../results/a/q2-nikolastarx/frontier-benchmark-s59ee-20260925/20260924T1827Z-s59ee/board-feed-500.json)
contains per-cell plans, evaluation artifacts, input and source identities,
timings, and official single-core baselines. Its fixed run used runner
`861a1f32073ba714a1bde555cea5d53f10a26b21`.

Arithmetic means of per-case baseline speedup for cores 1–5 are 1.108597×,
2.021385×, 2.736192×, 3.309358×, and 3.768826×. Against the earlier fixed
`b7c05...` batch, this version improves the mean at 1–3 cores but regresses
at 4–5 cores (earlier 3.320048× and 3.825059×). This is a complete candidate,
not a claim of all-case nonregression or a splice of historical winners.

New entrypoint: `python -m src.q2_nikolastarx.adaptive_frontier`. This is a new
algorithm version requiring its own complete 100×5 evidence, not a change to
the fixed b7 results or a selection of historical winners.

The existing resource-word, reduction-tree and vector guards are retained.
Where the old general route used only the number of components, compute each
component's mandatory work per Pipe and compare the largest with the balanced
whole-graph work per Pipe, `ceil(total_work/cores)`. If a component exceeds that
target, use the existing tensor-aware DAG constructor to allow internal splits.
This detects an indivisibility obstruction; it does not prove that the graph
admits enough parallelism, that the balanced target is attainable, or that the
new official score improves. COPY and memory costs may outweigh load balance.

Otherwise, if external tensors reused across components exceed a memory-pool
capacity, attempt the guarded shared-input wave construction. It matches full
component signatures and schedules the dependency closure of corresponding
shared-input consumers across local components. Unsupported templates retain
the old component-envelope construction. It may still have an oversized
activation frontier; raw touch peaks are not runtime zero-spill certificates.

There is no tunable threshold or case-name selection. Each selected mechanism
constructs one plan, without online E0/E1/E2. The inherited vector-cut repair
can still replace the general proposal with one structurally triggered plan;
both construction steps are included in solver wall time.

Static 056/k5 diagnostic: existing source DAG construction changes the fixed
compute-FIFO lower bound from 253,026 to 67,967 cycles; mandatory assigned Pipe
work is 51,826 cycles. Its independent-COPY timing proxy is 109,810, compared
with the old measured official 253,392. These are different quantities. The
proposed crossing traffic is 7,038,604 B, so real communication may dominate;
no measured improvement is claimed before E0. This pilot is particularly useful
for deciding whether to develop the more local attention-row construction.

Validation so far: meaningful synthetic routing, coverage and wave-lifetime
checks, plus static original-graph constructions. Official performance and
all-case nonregression remain unverified. Frozen old b7 data remain unchanged.
