# R9 layered ownership, 005 / five cores

One authorized official diagnostic ran on source `e9ff04c3019dedadd5b2ff71ecfdd57ac1aabe4a`, using the fixed candidate `2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a`. Both official calls completed. This is one candidate on one graph, not an integrated solver or a new full500 score.

| Quantity | Fixed Forest control | R9 candidate |
|---|---:|---:|
| P3 Makespan | 30642 | 24522 |
| Same-plan P2 Makespan | 37327 | 29026 |
| G = P2 / P3 | 1.2181646106651003 | 1.183671804909877 |
| Official-singlecore / P3 | 3.1204882187846747 | 3.8992741211972923 |

P3 cycles decrease 19.97258665%; P2 cycles decrease 22.23859405%. The conservative diagnostic joint acceptance flag is false because G decreases, despite both execution modes becoming faster. This is useful positive evidence for Makespan and negative evidence for nonregressing per-cell G; neither result should be discarded or relabeled. No no-cache degradation was used to manufacture a ratio.

The independent guard on actual captured Task/Step2/Step3-preparation data passed: 4113 original compute operations, 5135 prepared operations, 1022 COPY operations, 381 cross links, 5763 memory dependencies, 17905 unique union edges, and maximum complete-path crossing count 4. Prepared frontier peaks match the static certificate. These are preparation/local memory observations, not a separate measurement of final multicore peak memory.

Official scheduled COPY bytes are 1595646, of which 1262232 are partition-added and zero are spill-added. Cache hit bytes are 356084 and miss bytes 870442; byte hit rate is 0.2903191615995095. Scheduled COPY bytes must not be relabeled as measured physical DDR traffic.

The external supervisor observed T0 `2026-09-25T14:18:31.333313Z` and T1 `2026-09-25T14:18:47.451614Z`, exit 0, wall 16.217289542 seconds. Worker diagnostic times are P3 8.403244792 seconds and P2 7.181347334 seconds; these include observation and prepared auditing and are not cold end-to-end solver times. `solver_wall_seconds` remains null. Exactly one P3 plus one conditional P2 E0 were entered; both phase exits are 0. The two-call budget is spent; no retries or further evaluations are authorized by this report.

All 18 resource samples had memory-pressure level 1 and no other visible scorer. Maximum sampled owned-group RSS was 218726400 bytes (208.594 MiB), swap-used growth was zero, and final owned processes were empty. The root's separate `ps` readback of PIDs 85095, 85105, and 85747 also returned no rows. Sampling every second is not a hard peak guarantee. Low physical-free memory did not prevent this bounded diagnostic from completing safely.

Original `run/` and `resource-control/` receipts, claims, stdout/stderr, compressed official results and captured preparation are preserved. The admitted manifest and admission decision were copied locally without changing their bytes. The initial mistyped pathname in an auxiliary hash command did not launch or retry a scorer; the actual admitted manifest and supervisor hashes matched.

The separate 100-graph recognition audit finds 22 decomposable graphs, with only 13 satisfying the current five-core subset-DP track-count requirement. Under the explicit hypothesis that the other 87 retain the fixed Forest solver and 005/086 use these exact plans, even combining optimistic legitimate bounds yields a mean ceiling below 5; see `../layered-target-impact-20260925/INDEPENDENT_CEILING_REVIEW.md`. Therefore broader structure coverage or a materially different construction is necessary. This is not an impossibility result for P3 or for the whole algorithm family.
