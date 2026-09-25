# P3 left-deep tile: one delayed ADD and two different certificates

Scope: static proposal, no official Task/Step2/Step3/evaluator execution.
Source anchor: Vioano/huaweicup2026 @ 8e4143209709f7c9a78bf134b36ab8ddef8f01fb.

## What was actually checked

The mounted original attachment contains data/case_097.json. Its exact bytes
have SHA-256 7dc5c8ebf92052dbdd1bf59794a8fcef74e3ab3c59d5f0b4e753bf38a741ffaf,
matching the new fixed profile. The static recognizer checked all 64 original
left-deep trees and the per-position A/B tensor identities. No nonexistent
expanded GitHub case JSON was fetched. The original graph is not repackaged.

The candidate preserves owner=core0 for every original computation in this
one-core case. Subgraphs remain original-operation singletons. Only order
changes. No start times, buffer addresses, new arithmetic nodes or changed
reduction associations are submitted.

## One construction

Traverse original chain position, then cells in each owner-intersected tile.
After each M emit the previous leaf's pending original ADD, then set the pending
ADD to the current leaf's original ADD. The first leaf has no ADD. Drain the
last pending ADD at tile end. An ADD is delayed in the priority WORD, not
assigned an artificial start time.

Tiles never migrate a tree. The shape search is the finite two-dimensional
shape family; it does not search assignments or call an evaluator. Let N be the
number of original operations and H=m*n the number of proposed shapes. The
simple implementation costs O(H*(N+E)); each tile's future-use envelope uses
sliding distinct-input windows, plus heap operations for lifetime endpoints.
More precisely its implemented heap bound is O(H*(N+E) log N). Output and static
verification are linear apart from deterministic sorting. No claim is made
that this is exact optimization of all legal P3 words.

## Certificate 1: future-use envelope (Step2, not execution time)

At compute position j, include all live original computed outputs at the
alloc-before-free instant. For every output and each input already used in this
tile, take its last use within the tile as a protection deadline. Let H(j) be
the largest such deadline. Count ALL distinct external input keys used in
[j,H(j)], including upcoming-position keys that might remain from an earlier
tile. Let E(j) be this input mass plus live computed-output mass.

If max E(j) <= L1 capacity, the frozen farthest-next-use Step2 rule cannot evict
one of those protected objects: any extra resident object needed to cause
an overflow must have next use later than H(j), so it is selected first.
Induction gives no spill of original computed outputs and no second reload
of a key during its uses in one tile/chain-position block. External input
residues MAY be evicted and reloaded. This is NOT a zero-total-spill theorem.

Conditions: exact ports, each input key belongs to exactly one chain position,
whole-tree owners, no interior COPY, singleton bucket order, root COPY_OUT in
the root bucket, unique external COPY_IN DDR backing, and the frozen Step2
rule. All generated local tensors in this prototype are guarded to be L1.
COPY_IN steps before their first M are dominated by that M's envelope; root
COPY_OUT steps introduce no new L1 tensor. Other tensor types need new guards.

A smaller 'current tile/layer fits' bound is NOT this certificate. It omits
already-resident keys whose next use is in the upcoming layer. For 097, 4x8
passes the simple current-layer bound but fails the future-use envelope by
2048 bytes. The selected 8x4 passes at 518144 bytes, without a tuned margin.

The resulting Step2 input-COPY bound is 6815744 bytes and the input-reload
bound is 2555904 bytes. These are theorem predictions to independently audit,
not observed E0 output. Fixed root output COPY bytes are separate. The total
extra-COPY upper bound is also 2555904 in this one-core, guard-compliant case.

## Why this still does not prove M improves

Step2 uses NEXT-use priorities. Step3 credit reuse waits for PREVIOUS readers
to finish. A permissible residue eviction can target an input still read by
the currently running M. The next input COPY or ADD may then wait, producing
short feedback paths that accumulate over many M slots.

The number called `conditional_service_envelope` is only a ranking objective
in a reserved-buffer model: no extra credit-reader gates, one pending ADD,
M duration >= V duration, total input/output service charged conservatively,
and tile-end ADD drains. It is NOT an official Makespan bound. Do not report
10559344 as a predicted official result.

## Certificate 2: already prepared execution graph

m_debt_certificate.py consumes an exported official prepared graph, including
physical incarnations, all MEMORY_REUSE edges, all four FIFO words and cross
links. It does not build Tasks or call Step2/3. The caller must validate source,
plan/config identity and the complete official execution contract.

For each COPY, the optimistic duration assumes the fastest legal pool; the
pessimistic duration uses at most 2k DDR copies or k cache reads sharing a pool.
Two DAG passes bound every completion time and therefore startup plus cumulative
M idle, not just the maximum individual gap. The potentially dense M-anchor
projection is explanatory only; the checker works on the original expanded DAG.

No prepared graph for the new case097 candidate was supplied or generated in
this run, so no official-timing certificate has been issued for it.

## Files / invocation

- leftdeep_tile.py: guarded static owner-preserving constructor
- case097_k1_candidate.json: unscored 2-field candidate
- case097_static_certificate.json: raw hash, algebraic and envelope checks
- raw_chain_samples.json: a few original-node/port coordinate samples
- m_debt_certificate.py: checker for an already prepared graph
- checks.py / abstract_wait_checks.json: 3 hand-constructed DAG checks

Use an existing singleton baseline plan for the required owner:

    python leftdeep_tile.py ORIGINAL.json BASE_PLAN.json NEW_DIRECTORY \
        --capacity 524288 --bandwidth 60

Then compile only this one candidate with the unchanged official code, verify
the Step2 predictions, export the prepared graph and run the debt checker.
Do not rerun official compilation for every tile shape.

All original arithmetic and all original tree edges must remain unchanged.
