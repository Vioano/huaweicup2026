# Frozen structural runner: two-cell pilot

This is a runner/receipt pilot, not a full-matrix algorithm score. Both cells freshly ran solver `3a1b82b71ca1ff6689eb8e72f17d26c48b52073c` with runner `8335b5c55b0c12bd34b206e315582d1198439069`. No production solver was changed. Fixed official source/config/archive hashes and the complete command appear in `public/batch.json` and the public supervisor receipts.

| Cell | Official Makespan | Scheduled DDR bytes | Solver wall seconds | E1 calls | E0 evidence |
|---|---:|---:|---:|---:|---|
| 001/K5 | 47502 | 1644160 | 0.141940917 | 0 | Prior v4 E0, exact input/config/code/plan bytes and receipts checked |
| 051/K5 | 231551 | 9437954 | 0.598147916 | 4 | New official E0, 0.200204333 s |

Both saved plans contain exactly the two official keys. Calls: **2 solver, 4 E1, 1 new E0, 1 prior E0 reuse, 0 E2, 0 scoring retries**. The selected 051 plan hash is `d7de42f7eea7ca83787244b2307448d6d34b5b61045fd902fb2a97540b8ed5e2`; this closes its earlier lack of a local official receipt. Neither cell represents a new best result by itself.

The initially delegated outer wrapper failed at 00:34:19–00:34:20 UTC before starting the runner because it invoked `python` through PATH. Actual solver/evaluator calls in that attempt were zero. Root corrected the wrapper to use the locked absolute Python 3.12.13 interpreter; the failed attempt is retained separately. Wrapper restarts: 1. The directory label `0038Z` was reserved before launch; authoritative times are the receipts: successful supervisor **00:36:17.030–00:36:21.168 UTC**, with 4.138510084 s outer wall; runner 3.400288291 s includes source/baseline preflight. Its `started_at` field is recorded after preflight, so subtracting runner timestamps alone omits that work.

One worker, one configured thread per child; fresh interpreter per cell, OS caches not flushed. One-second process-tree samples observed a maximum **198016 KiB**, not an upper bound on true peak RSS. The 8 GiB sampled stop line was not crossed and no observed owned process group remained. Per-cell solver limit 300 s, new E0 limit 900 s; no full500 was started. `maximum_calls` in the reusable runner metadata is its full500 ceiling; the actual authorized selectors restrict this pilot to 2 solver/18 E1/2 new E0, not 500 cells.

`public/artifact-map.json` maps large raw JSON to deterministic gzip copies and records both hashes. Run receipts retain their original raw paths/hashes; consult that map to locate compressed public bytes. Supervisor copies substitute personal paths only and record original and public hashes. Raw local material remains untouched. Independent read-only review checked the two-key outputs, per-cell metrics, reuse/new E0 distinction and total call ledger; it was not an independent rerun.
