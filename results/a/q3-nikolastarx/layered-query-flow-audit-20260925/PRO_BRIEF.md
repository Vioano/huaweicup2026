# Narrow mathematical question: layered query affinity with bypass paths

This packet is for a new mathematical consultation, not permission to run an
unbounded search or to reuse a teammate's in-flight Pro chat.

## Actual submission and evidence

P3 uses only `node_to_subgraph` and `core_schedules`. Original operations cannot
be fused, duplicated, deleted or moved to invented resources. Each M/V pipeline
has its submitted FIFO order. Official Task reconstruction, physical L1/UB,
spill, COPY engines, fixed cross-core delay and read-only cache remain active.
The official source/configuration is authoritative; see
`docs/a/OFFICIAL_OBJECTIVES.md` and `src/q3/query_flow_probe.py`.

The R8 constructor `src/q3/query_flow.py` recognizes one shared upstream stage
and private P/A/O flows, permitting only recognized P-to-A K/V cross-flow edges.
Its two-remote-edge path certificate and full-tensor-support capacity guard
apply only inside those explicit guards. They are not general lower bounds or
necessary conditions for all legal P3 plans. It currently only covers flow
count at most core count plus one.

The 071/K5 plan is now actually evaluated: P3 7782→5785, matching no-cache P2
8581→7070, G 1.102673→1.222126; zero spill. Result bytes and source comparison
are in `../query-flow-one-shot-20260925/`. The outer process supervisor failed
its terminal identity check after both official workers completed; all original
receipts and that limitation are retained. No new complete algorithm benchmark
has been produced. R8's 069 plan remains static and unscored.

## Concrete obstruction

`REPORT.md`, `audit.py`, `005.json`, `086.json` and `summary.json` in this
directory provide original-edge, non-scoring observations:

- 005 has 42 recognized rows, three depths of 14 rows; seven Q/K/V input keys
  per depth, two rows per key. 086 has three depths of 16 rows, eight keys each.
- Keys differ between depths. The first-downstream-row quotient has all edges
  0→1, 0→2 and 1→2: 196 edges per depth pair for 005, 256 for 086.
- A first-downstream edge stops before entering an intervening recognized row.
  Hence the 0→2 paths are real bypass dependencies, not merely transitive
  closure through layer 1. Complete original node-ID paths are saved.
- The old R8 guard rejects 005 because one recognized query row reaches a
  different flow. This is expected domain rejection; removing the guard is
  not a repair. No resident-capacity DP was reached and no new plan was scored.

Current same-fixed-solver five-core incumbents: 005 M=30642 and G≈1.218165;
086 M=32662 and G≈1.244566. These are historical official pairs from the
311322b full run, not new measurements. Compute-only bounds 12777 and 15837
are optimistic global relaxations, not promises that those values are feasible.
Improving only the exact two R8 plans cannot get the full five-core mean above
five (`../query-flow-target-gap-20260925/`). Broader structural coverage matters.

## Requested deliverable

Develop one implementable general construction for this layered, bypass-carrying
family, or a small counterexample showing why the natural construction fails.
Prioritize a precise bridge-node ownership/decomposition rule: every original
operation must have exactly one owner, all shared joins and bypasses must be
retained, and original per-pipeline FIFO must remain acyclic. Explain how to
recognize its domain from input structure without case-ID rules.

Then give a tractable assignment/order algorithm for 7–8 query streams on five
cores across three depths: e.g. a justified state compression/DP, canonical
grouping or direct load/communication construction, not an unconstrained grid
search. Account for complete-path remote crossings across all depths instead
of inheriting R8's single-depth constant. Distinguish exact properties from
ranking proxies and show one falsifiable prediction against the incumbents.

Capacity needs special care: the union of all tensors ever touched by a core
is sufficient but may be much too strict across layers. If proposing a weaker
live-frontier certificate, state exactly which official incarnation, allocation,
Task and FIFO assumptions it uses; do not silently assume arbitrary allocation
or zero-copy inter-core transfers. Otherwise keep a conservative guard and
describe the coverage it sacrifices.

Do not optimize G by inflating its P2 numerator. A candidate must reduce P3
cycles and avoid worsening its own no-cache baseline relative to the old plan;
report any G tradeoff explicitly. Cache byte hit rate alone is not a cycle
objective. Supply a minimal toy proof/counterexample and at most two specific
official validation candidates, with complexity and stop conditions.

List exactly which source files and original graphs were actually read. Missing
access must remain missing; do not report inferred code as inspected or invented
experiments as measured. This request does not ask to solve every P3 graph or
prove global optimality of the existing solver.
