# P1 unified solver: four-cell smoke export

This is a **4/100 graph preview at five cores**, not a full-matrix score or attainment claim. All four attempts completed with no retry or failure. The complete batch used 4 solver starts, 9 internal E1 calls inside solver wall time, and 4 separate external official E0 calls. The E1-selected plan's Makespan and complete movement object equal the external E0 result in each cell. `board-feed-20260924T1800Z-unified4.json` is a standard `board-submission-v1` export; no solver or evaluator was run for export.

| Case | Selected | E0 Makespan | Solver wall s, internal E1 included | External E0 wall s | E1 calls | Official singlecore E0 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 051 | fork-frontier | 253856 | 0.5096143329865299 | 0.26890900000580586 | 2 | 607628 |
| 044 | shared-input | 64624 | 0.5092587920080405 | 0.266724583983887 | 2 | 154407 |
| 031 | bounded | 306213 | 2.238551207992714 | 4.42275804100791 | 3 | 1414369 |
| 008 | bounded | 100603 | 0.38803437500610016 | 0.14311479101888835 | 2 | 487605 |

Source implementation: `48faef6f1386c3dc7d037674a38af29d533ba774`; actual runner: `00cc7d9587fc760203bf2796d938458e2712bdf4`; Python 3.12.13 on Apple M5 Pro/macOS. The official singlecore results were copied byte for byte from commit `6fcec11ccc472a1a652b21feb6fccf85a4555598` after graph, config, and official source identity checks. An optimized k=1 plan was not used as denominator.

The committed `plan.json` files retain original bytes. `result.json.gz` and `trace.json.gz` decompress to the exact original bytes; original and compressed SHA-256 values are in `export-receipt.json`. The committed `run-derived.json` files replace local absolute argv paths and retain each original run SHA-256. Original run receipts, process logs, and RSS samples remain in the local batch directory; **they are not claimed as Git archived**. This derivative status limits independent verification of raw command paths. The original batch directory has not been overwritten.

The board precheck validates format and available bytes only. It does not independently rerun official E0 or prove a 100-graph fixed-algorithm result. No central enqueue, website admission, or team notification is part of this export.
