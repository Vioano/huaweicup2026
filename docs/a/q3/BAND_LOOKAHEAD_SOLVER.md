# Band-DP + one-leaf lookahead candidate

This is one fixed mechanism candidate, not a full-500 result. It composes the already reviewed Cartesian forest band-DP with its `pair_cache_model` tree order, then applies exactly one leaf lookahead to each eligible singleton plan. It does not choose between axis-reuse alternatives, search lookahead depth, or use case identifiers.

The lookahead preserves the node-to-subgraph map, operation owner, and each core's PIPE_M and PIPE_V projections. It requires singleton subgraphs, only original PIPE_M/PIPE_V compute ops, and no compute predecessor for every PIPE_M operation (`Index.pred`; external COPY_IN dependencies do not count as compute predecessors). Its shifted V block is a static ordering/frontier condition only, not an L1/UB capacity or performance certificate. The composed plan is checked by `derive_multicore_plan`.

`band_lookahead_solve` first calls `forest_solve.evaluate_candidates` to obtain a fresh incumbent. It may then construct at most this one combined plan if the cumulative E0 count remains below three. Canonical encoded-plan equality skips duplicates; the frozen `pipe_bound` may safely prune when its lower bound is at least the incumbent M; unsupported bounds do not suppress evaluation. Official evaluation is the acceptance gate, and only strictly lower Makespan replaces the fresh winner. `main` keeps `candidate_limit=3`.

The bounded record motivating this candidate reported:

| Case / prior plan | Prior M | Same owner + one-leaf lookahead M | Change |
|---|---:|---:|---:|
| 058, band-pair | 925,513 | 897,619 | −27,894 |
| 079, band-pair | 6,165,618 | 6,006,541 | −159,077 |
| 079, forest-memory | 6,075,472 | 5,984,184 | −91,288 |
| 058, forest-memory | 1,004,819 | 1,031,313 | +26,494 |

These are mechanism samples, not all-500 evidence; the reported four comparisons also had increased spill. Reproduction tests compare 058/079 plans byte-for-byte against the saved band-pair lookahead plans and inject policy outcomes without calling E0. Use `PYTHONDONTWRITEBYTECODE=1 uv run --locked python -m unittest tests.q3.test_band_lookahead_solve -v` for the bounded tests.
