# Attention placement witness word

`construct(..., final_order="placement")` retains the start and finish times of
each accepted capsule trial. It sorts all original compute operations by
`(start, op ID)` and projects that one global word onto each core. The default
`final_order="ready"` keeps the previous fixed-owner ready pass and metadata.
The `placement` result keeps the same singleton mapping and ownership; it does
not fuse operations or add a whole-core timing barrier. Metadata identifies
the order, reports each committed start/finish witness, and uses its maximum
finish as `proxy_makespan_cycles`.

The bound is limited to the model used by the constructor: positive compute
durations, original compute dependencies, one FIFO for each M/V pipe on each
core, and a fixed delay for cross-core dependencies. Every dependency has
`start(v) >= finish(u) + delay`, so positive duration gives
`start(v) > start(u)`. Nonoverlapping reservations on the same pipe also have
strictly increasing starts. Sorting by start therefore keeps both the
original dependency order and each pipe's reservation order. The projected
word is topological, and an independent ASAP calculation on the dependency
plus per-pipe FIFO graph has start and finish times no later than the feasible
committed witness. Its makespan is at most the reported witness proxy.
Sorting the witness and projecting it costs `O(V log V + E)` including the
dependency-order check, beyond the existing capsule placement work.

This is a proxy-model bound, not an official E0 bound or an optimality claim.
Official COPY scheduling, Task ordering, DDR/cache behavior, and capacity can
change the result. The option does no online final evaluator selection.
Structural tests cover 60 fixed combinations of row panels, FFN diamonds,
duration imbalance, shuffled IDs, and 1–5 cores. They independently rebuild
the dependency and per-pipe FIFO timing graph and compare it to each committed
witness. No E0/E1/E2 call is part of these checks.

## Online policy and observed proxy gap

`src.q3.witness_solve` preserves the complete fresh `pipeline_solve` incumbent.
On multi-core Attention routes it considers exactly one placement word only if
the gap candidate's committed witness proxy is strictly smaller than its ready
reranking proxy. This screen is intentionally model-based, not a certificate
that an excluded word could never improve the official score. If the previous
policy already consumed3E0 calls, no extra proposal is evaluated. Duplicate and
certified E0 lower-bound checks can skip scoring; actual acceptance requires
strictly smaller official Makespan. Whole solver maximum remains3onlineE0.
No case IDs or historical score lookup enter this decision.

From the frozen831 full500 candidate receipts,108 gap candidates contain both
proxy values:47 have a smaller placement witness and61 a smaller reranked proxy.
This is mechanism evidence about the current constructor, not official witness
performance. Current default plan plus metadata were compared exactly with the
87f677 constructor on066/082/071 at5cores. Ready versus witness proxies are
71326/58542,147928/133160,5441/5218 respectively; the latter are feasible
simplified-model witness times, not measured official makespans.

Result storage also reuses the compressed winning payload only when a fresh
encoding's SHA-256 matches the saved payload. The cache retains one compressed
candidate, not all raw result dictionaries. A different/mutated result falls
back to fresh compression. Fake-evaluator CLI tests check exact gzip bytes and
fallback behavior; no full solver runtime improvement is claimed before timing.
