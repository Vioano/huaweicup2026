# P3 expanded_solve: complete 100 × 1–5 core benchmark

This is one fixed algorithm version, not a selection of per-case historical
winners. The solver source is `a5dafdf94d0694132fb9ec7121f5fe1fe0d6ee3b`
with entrypoint `src.q3.expanded_solve`; the execution controller is
`b57ae6d3a4038343819dd842ce871d5e42cb5578`. The ten disjoint 50-cell
shards ran between 2026-09-24 18:37:19 and 18:43:00 UTC, with a four-cell
pilot and at most eight concurrent shard processes. They produced 500/500
plans and 500/500 independent, unmodified official P3 E0 evaluations. The
solver used 755 online official P3 E0 calls, zero E1/E2 calls and zero
retries. All ten shards completed and their process cleanup was confirmed.

The [standard board feed](../../../results/a/q3-nikolastarx/expanded-full500-20260925-s59/20260924T1837Z-s59ee/board-feed-500-with-baselines.json)
includes the matched official single-core baseline for each case. The 100
baseline result/run originals were copied from fixed commit
`6fcec11ccc472a1a652b21feb6fccf85a4555598` with byte and hash checks.
The feed SHA-256 is
`6961a9a1f382a7cdf823686e5ac72198bdf145e2d0516f6533ae272a10539541`;
fixed-commit `protocol.py --submission` validation reported 500 records and
500 eligible cells. The raw feed without baselines is intentionally excluded
from submission because it cannot yield comparable baseline speedups.

Arithmetic means of per-case official baseline speedup for 1–5 cores are
1.199407×, 2.287559×, 3.184366×, 3.987203× and 4.595235×. Against the
earlier fixed P3 source `2d545...`, the new version improves 160 paired cells,
ties 340 and regresses none. This comparison is across two complete fixed
batches; it does not splice their plans or scores. It does not establish a
causal Cache benefit, which would require paired no-Cache P2 evaluations.
