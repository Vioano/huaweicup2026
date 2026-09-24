# Intact fork/join construction with variable graph dimensions

This experimental constructor adapts Fang's source-core pacing (J,
`aa3f18a71b117ebd0476c8d714c97d8d366d74d7`) and intact prefetch/subtree fusion
(H, `4f1b9f8be4bbcc98759a19451c108e62e80abb17`). The fixed copies reviewed are
in `08e5cbf96c57bbfb603ec9661ee591e2adb8c26f:src/q1_yuanzhifang_stage_k/`.
The new implementation is `src/q1/intact_frontier.py`; it does not change the
existing production solver or Fang's source files.

## Recognition and construction

Recognize a sequence of fork/join rounds from actual compute dependencies.
Each round contains at least two serial chains and a binary ADD reduction
tree. The previous round's root is the only predecessor of each new chain's
first operation. Every chain leaf has exactly one successor in that round's
reduction tree, each non-root reduction has one successor in the tree, and
the unique root feeds exactly the next round or terminates the graph.
All compute operations must be covered exactly once. COPY contraction must
not introduce retained compute dependencies omitted by the recognizer.

The current domain requires PIPE_V compute and equal ordered operation/cycle
descriptors for the chains within each round. Round count, chain count and
chain length come from the graph; they can vary between rounds. The restriction
to homogeneous chains motivates count-based packing, not a timing theorem.
Tensor sizes, FIFO order, spill and shared DDR remain part of official scoring.

Two deterministic constructions expose different mechanisms:

- `paced`: assign consecutive whole chains to balanced groups. After the first
  round, if core zero owns at least two chains, emit its first chain as an early
  Task and its remaining chains as a second Task. Emit the reduction tail last
  on core zero. Other cores retain one whole-chain group per round.
- `root-heavy-fused`: initially use at most K−1 cores. In later rounds assign
  floor(W/K) chains to each other core and the remainder to core zero. In each
  group fuse only the topological closure of reductions whose compute inputs
  already belong to that group. Emit the remaining tail on core zero. Omit
  empty groups and omit a residual tail when every reduction is already fused.

These rules generalize H/J's placement choices. They do not assert that K−1
startup cores or a heavier root core is best for every graph. An independent
candidate score and baseline fallback are required before integration.

## Structural legality argument

Each chain belongs wholly to exactly one group. Pacing divides a group between
chains, never within a chain. Fusion assigns a reduction only after all its
retained compute predecessors have been assigned to the same Task; therefore
it introduces no dependency on another frontier Task in that round. Distinct
groups cannot fuse the same reduction. The residual tail contains all remaining
reductions and depends only on completed frontier groups or earlier reductions
inside that tail. The graph recognizer's exact coverage check rules out omitted
or duplicated compute operations.

Give every Task rank `(round, phase)`. Paced frontiers have phase zero, the
second root-core group phase one, and the tail phase two. Fused frontiers have
phase zero and the residual tail phase one. All inter-Task data dependencies
strictly increase this rank: they either go to a later phase in the same round
or leave the previous root for a later round. Each core's order also strictly
increases the rank. Thus the union of data dependencies and core-order edges
is acyclic. An entirely fused tail ends in phase zero; all its outgoing edges
still advance to the next round. No empty Task is needed in this case.

The implementation checks this union explicitly in addition to the official
plan derivation and Task-order validator. This matters because the official
validator has a singleton-core-order early-return path. It also rechecks
complete coverage and that no chain was cut. This establishes the claimed
structural property for accepted graphs; capacity feasibility and successful
official execution still require their own evidence.

Recognition visits chains and reduction edges once, with heap-based topological
ordering. Fusion scans each tail at most K times (K≤5). The complete constructor
also calls the unchanged official graph/plan validators; no linear end-to-end
complexity or E0 improvement claim follows from this traversal description.

## Validation scope

The first implementation ran four small synthetic tests with nine constructor
calls. Root review removed repeated linear membership scans and repeated set
unions; the same nine calls then passed again. These 18 constructions used no
official case, Task compilation or evaluator. Shapes include variable width
and depth, one and multiple rounds, balanced and comb reduction trees, fewer
chains than cores, a fully fused tail, and rejection of cross-chain/hidden COPY
dependencies. They verify construction invariants, not unseen-graph performance.

Real-case transfer and any later unified selection must be recorded separately
at their actual frozen source, with full solver wall time and E0 evidence.
