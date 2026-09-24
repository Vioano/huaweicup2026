# Forest P3 plans paired with no-L2 P2

The fixed `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1` forest solver produced 500 P3 plans. The [frozen mapping](../../../results/a/q3-nikolastarx/forest-cachepair-delta-20260925/manifest.json) identifies 476 byte-identical plans already evaluated under P2 and 24 plans requiring one new official P2 evaluation each. It does not create new P3 or solver evidence.

Forest plans, receipts and P3 results are pinned to artifact commit `bff88a66cd76ceb2d75242bf99d34bfe8b1879d4`. Prior C2 P3 plan bytes are pinned to `f0ead1a3722f70a59a084acc70700a963945b567`. Existing P2 result bytes are pinned to **`11d5d3ba1820864626bb49acccbeec7a75553e80`**. The C2 P3 artifact commit is not the P2 result artifact commit. Every manifest path is relative to the repository; a producer checkout is supplied at execution time.

After the controller and manifest are reviewed and committed, run the read-only preflight in the execution checkout:

```sh
python -m src.q3.cache_pair_delta --forest-root /path/to/forest-producer-checkout --preflight
```

Preflight runs **zero E0 calls**. It checks the execution HEAD and relevant tracked diff, controller/oracle/official code hashes, all 500 coordinates and original graph/config identities, exact two-field forest plan bytes against the pinned commit, forest P3 receipt and result identity, and the 476 reused P2 result blobs. It compares the forest and C2 plan bytes for reuse. An uncommitted controller or manifest fails preflight by design.

To run only the 24 missing P2 evaluations, choose a new output directory under `results/a/q3-nikolastarx/forest-cachepair-delta-20260925/` and pass it with `--batch`. The controller uses one worker, one `python -m src.q3.oracle graph plan 2 output` subprocess per job, at most 90 seconds per job and 1800 seconds including preflight for the batch. It makes no solver or P3 calls, never retries, and stops at the first timeout or failure. Each job retains its exact plan, stdout, stderr, result hash, wall time and status; the batch retains its call ledger and execution HEAD. A job's wall time is external official reevaluation time, not solver time.

The 476 reused P2 measurements remain historical. A complete paired 500-row report is justified only after all 24 new cells succeed and their result identities are checked. This pairing does not by itself establish a new fixed solver's all-500 score or speed.
