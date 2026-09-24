# Chain pilot evidence audit

Read-only audit of six fixed candidate plans. Candidate mapping insertion order and schedules match manifest-pinned Git plans. For each case, E2 record equals independent E0 result on Makespan, all five movement fields, and cross-task traffic; baseline fields match manifest-pinned existing E0 bytes and run summary. All six processes exited 0, left no surviving PIDs, and both in-flight flags are false. Totals: E2 6, native 6, fallback 0, independent E0 6.

| Case | Candidate M | Baseline M | Delta M |
|---|---:|---:|---:|
| 003 | 269209 | 515736 | -246527 |
| 005 | 72375 | 66385 | 5990 |
| 056 | 148632 | 253392 | -104760 |
| 068 | 159409 | 295114 | -135705 |
| 086 | 94865 | 102180 | -7315 |
| 088 | 106272 | 200888 | -94616 |

Only these six fixed cases are described. No full algorithm mean and no constructor wall claim. Official trace JSON passed basic traceEvents structure validation. Original JSON files were removed only after deterministic gzip roundtrip SHA verification; see archive-manifest.json.
