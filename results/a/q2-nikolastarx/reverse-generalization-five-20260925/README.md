# Reverse candidate: five unseen structures, not a full benchmark

Owner: nikolastarx/s-7d28768dcd7d4e0e8759c2afd02659d5. Source `675fdcb4f6527336f35ca3ec870bf59544485324`; historical s8ee text in the frozen VM/package name is only an artifact label. One admitted run, 5 constructor + 5 unchanged external E0, no E1/E2/retry. No online selector was executed.

| Case K5 | Old M | Reverse M | M reduction | Old/new extra DDR bytes |
|---|---:|---:|---:|---:|
|010|20820|25408|-22.04%|316892 / 1065476|
|064|11274|10737|4.76%|93940 / 92016|
|086|41466|57041|-37.56%|1720856 / 2905336|
|068|134367|129330|3.75%|4469970 / 4180054|
|088|93547|90708|3.03%|3182080 / 3006944|

All five evaluated; zero spill. Three positive and two negative results retained. These graph choices preceded this run; this is a targeted mechanism set, not a random generalization estimate or full500 score. Reverse alone must not replace the seed. The separately implemented four-score online wrapper still needs real end-to-end qualification; its lexicographic objective does not guarantee DDR non-regression and an uncertain E2 request can fail closed.

Actual T0 2026-09-25T11:30:38Z. Cloud scoring 11:31:16.796012–11:31:36.749582Z, Python3.13.15/Linux x86_64; see bootstrap inside results.zip. Project normal dependency target is Python3.12, so this cloud probe is a distinct environment, not a Mac solver timing claim. Peak observer-inclusive RSS243384320B. Named VM stopped, fresh session list empty, watchdog absent, no surviving children. Original raw host process list is retained privately; public gate receipt omits unrelated commands and records the original hash. No reset/retry and no further window implied.

`results.zip` retains every plan/result/solver/trace/process/log; capsule contains fixed source/config/raw input and authentic commit object. `parent-verification.json` records independent hash/metric/baseline and release checks. Run `python3 results/a/q2-nikolastarx/reverse-generalization-five-20260925/verify-archive.py` for offline artifact checks (zero scoring, no cloud calls). Exact original runner commands are in each process.json. Formal result remains c665 full500 K5 mean4.549756996698352. No board-feed is provided.
