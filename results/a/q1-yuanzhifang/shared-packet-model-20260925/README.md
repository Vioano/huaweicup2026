# Shared-input packet pipeline: unscored structural model

The fixed original 044 graph has 11 homogeneous jobs, 124 compute positions per
job, and 50 external inputs shared at the same position of every job. This
diagnostic reads graph metadata only: no real submission plan, official Task
compiler, E0, E1 or E2 was run to produce `044-model.json`.

Each rectangle contains a contiguous range of positions and a packet of jobs.
A stage is assigned to one core, which executes its packets in order. A compute
edge remains in its rectangle or advances the stage; a core-order edge advances
the packet. Thus `stage + packet` strictly increases on every inter-Task edge,
proving the augmented Task graph is acyclic. This does not prove official
performance. All non-DDR tensor identities incident to a rectangle are charged
to its memory-space union; original DDR compute tensors are charged to UB.
Shared inputs count once, while the largest individual job-local union times
packet size gives a conservative memory allowance. It can be overly restrictive.

The model enumerates at most one scalar packet count per job, and computes a
capacity-constrained minimax interval partition by dynamic programming. These
are metadata alternatives, not evaluator calls or submission-plan trials.
Only the best model alternative is used by the subsequent constructor.
Its duration proxy combines dominant-pipe load, isolated COPY service and the
one-job critical-path tail; actual FIFO/DDR overlap can differ in either
direction. The subsequent flow recurrence includes same-core 100 and cross-core
1000 cycle waits. The maximum of flow time and aggregate COPY service is a
selection heuristic, not a Makespan bound. The minimax DP does not globally
optimize the later flow/DDR objective, and its tie-breaking sum is not certified
globally minimal.

For 044, the best metadata alternative uses four stages, cuts
`[0, 28, 60, 86, 124]`, and packets `[4, 4, 3]`: flow proxy 47,221,
COPY-service proxy 49,494 cycles. Stage resident unions are at most
177,376 / 467,456 / 485,888 / 226,176 bytes of L1 (UB zero here).
These values are **not measured E0 results**. A two-packet alternative reduces
the COPY-service proxy to 34,228 but raises the flow proxy to 53,570, illustrating
the batching/parallelism tradeoff. The selected candidate must be frozen and
evaluated before claiming an improvement over the captain's 044 result.

Reproduction: `python -m src.q1_yuanzhifang.shared_packet_model GRAPH --cores 5
--output NEW_MODEL_JSON`. The checked input SHA-256 is recorded in the JSON.
Runtime includes graph parsing, table construction and DP when used inside a
solver; the current diagnostic has no complete solver-wall measurement.
No case ID, previous score or stored model result is used as an algorithm rule.

Guard review additionally rejects excluded COPY operations lying between two
compute operations, using full-op ancestry/reachability before constructing
compute-only components. Official nearest-eligible contraction preserves such
bridges, so ignoring them would invalidate the component-independence proof.
Three small synthetic tests cover structural/capacity validity, shape/sharing
mismatch, and this hidden cross-job dependency. No official evaluation is
performed by these tests.
