# Active-core 500 paired data audit

All ratios use the same verified official per-case single-core B_i. Each mean averages all 100 B_i/M_i ratios for the selected core count.

| Cores | Old mean | New mean | Wins | Losses | Ties |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.081752541 | 1.108596708 | 9 | 0 | 91 |
| 2 | 1.975047934 | 2.050483457 | 9 | 0 | 91 |
| 3 | 2.698614587 | 2.815665259 | 9 | 0 | 91 |
| 4 | 3.320047871 | 3.476781242 | 9 | 0 | 91 |
| 5 | 3.825058536 | 4.014094175 | 9 | 0 | 91 |

Total: 45 win, 0 loss, 455 tie.

Data commit `60afc38b327680fbda0ff10182e3e05a01edd72d`; clean data commit `85004b67147a8dfd0b556709b26a9ec41af4c721`; identical results subtree `b297a41fd2621a6835ecf7858c13a73a3897f239`. Unified feed `results/a/q2-nikolastarx/active-core-full500-20260925-s59/20260924T1910Z-s59ee/board-feed-500-with-runtime-notes.json` has SHA-256 `0b850686966d1d7c1ce1a8babb1655051756b42f9a59d5c6f6becd6a87f2f99c`. Verified 500 prior audited shard feeds and 2100 distinct original blobs against the fixed commit.

The paired audit checks graph/config/source identities, referenced result/run/plan hashes, DDR fields and each available manifest (500 new, 0 declared by old feed). No new solver or E0/E1/E2 calls. This is an evidence audit, not full independent algorithm acceptance.

Runner/controller Python 3.14.5; producer records solver and external E0 child argv using locked .venv Python 3.12.13. Runtime-notes feed preserves this distinction. Concurrent wall samples are not exclusive timing.

Reproduction: run `audit_active500.py --new-root PRODUCER_CHECKOUT --old-root REPOSITORY --new-shards PRODUCER_CHECKOUT/results/a/q2-nikolastarx/active-core-full500-20260925-s59/20260924T1910Z-s59ee`, then `freeze_snapshot.py`. Both scripts read existing artifacts; neither evaluates plans. Final summary/README come from the second script.
