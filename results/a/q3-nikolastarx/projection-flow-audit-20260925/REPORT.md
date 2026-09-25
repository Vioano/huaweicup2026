# Raw projection-key ancestry audit

The frozen one-process audit completed for original 005 and 086 without a scoring or construction call. It used `_ports.producer` for each distinct previously identified raw Q/K/V key and the producer's frozen first-upstream-row signature. Every proposed relation was checked with an original-edge path from the upstream row sink through the key producer to the key tensor. DSU groups these proven relations only; it does not erase other graph edges.

| Case | Distinct keys | Row-to-key path records | DSU groups | Keys per layer in every group | Same-layer collision |
| --- | ---: | ---: | ---: | --- | ---: |
| 005 | 21 | 42 | 7 | 1 / 1 / 1 | 0 |
| 086 | 24 | 48 | 8 | 1 / 1 / 1 | 0 |

Each later-layer key is linked by two recognized upstream rows sharing one earlier-layer key; the path records split evenly across depth pairs 0→1, 0→2 and 1→2 (14 each in 005, 16 each in 086). The 7 first-layer keys in 005 and 8 in 086 have producers but no upstream recognized row. No key lacked an original producer. Each DSU group contains two recognized rows at each layer, as recorded in the full JSON.

The resulting key triples are:

- 005: `(1000000089, 1000001512, 1000002935)`, `(1000000099, 1000001522, 1000002945)`, `(1000000109, 1000001532, 1000002955)`, `(1000000119, 1000001542, 1000002965)`, `(1000000129, 1000001552, 1000002975)`, `(1000000139, 1000001562, 1000002985)`, `(1000000149, 1000001572, 1000002995)`.
- 086: `(1000000091, 1000001901, 1000003711)`, `(1000000101, 1000001911, 1000003721)`, `(1000000111, 1000001921, 1000003731)`, `(1000000121, 1000001931, 1000003741)`, `(1000000131, 1000001941, 1000003751)`, `(1000000141, 1000001951, 1000003761)`, `(1000000151, 1000001961, 1000003771)`, `(1000000161, 1000001971, 1000003781)`.

For example, the 005 link from key `1000000089` to `1000001512` uses producer op `1450`, whose first-upstream row set includes row 0. Its checked original-edge path is `214 → 1000000250 → 1276 → 1000001312 → 1278 → 1000001314 → 1280 → 1000001316 → 1281 → 1000001317 → 1294 → 1000001330 → 1442 → 1000001504 → 1447 → 1000001509 → 1449 → 1000001511 → 1450 → 1000001512`. The parallel row-7 path and every other union's path are retained in `005.json`/`086.json`.

These triples are a useful **key-lineage anchor** for a future persistent-flow construction. They are insufficient as a legality or performance proof: the earlier row quotient has all-to-all reachability across layer pairs, and shared bridge, bypass, COPY, capacity, owner, FIFO and official timing semantics remain to be handled. A later constructor must preserve those original dependencies even if it assigns lane-like keys to fixed cores. This result is local static evidence, not adoption of an unfinished Pro conclusion.

`FROZEN.md` records code and input hashes. The script's stdout/stderr and full producer/signature/path records are preserved. Static analysis wall time was about 0.127 s; it is not solver time. Actual token use is unavailable.
