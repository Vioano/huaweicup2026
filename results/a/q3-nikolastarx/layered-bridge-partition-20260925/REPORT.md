# Nearest-row frontier partition of original operations

The frozen static process completed once for official 005 and 086. It assigns **every original op ID, including zero-cycle COPY ops, exactly once**. The 005 graph has 4,209 ops in 205 inventory components; 086 has 5,372 ops in 224. Sum of component `cycles` by original pipe exactly equals the input: 005 PIPE_M 63,882 and PIPE_V 60,930; 086 PIPE_M 79,182 and PIPE_V 78,060. MTE2/MTE3 original COPY cycles are zero. These cycle sums describe raw work, not runtime or simulated pipe occupancy.

For each non-row op, the signature contains every **first recognized row** reachable upstream and downstream along the original op DAG, stopping traversal at a row. The corresponding row depth and frozen raw Q/K/V key give a deterministic role: source, bridge, tail, or detached; row interiors retain their own row IDs. A bridge's `U…_D…` band records its upstream and downstream depth sets. `one_to_many` and `many_to_many` count distinct upstream/downstream Q/K/V keys in the signature. Within each label, weakly connected components are bookkeeping groups; they are not fused tasks or proposed placements. The full JSON records every op ID, component, frontier signature, and per-component work, so the partition and no-duplication check can be inspected independently.

| Case | Band | Original ops | Components | PIPE_M cycles | PIPE_V cycles | Bypass-tagged ops |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 005 | row L0 / L1 / L2, each | 1,120 | 14 | 9,840 | 14,962 | 0 |
| 005 | bridge U0→D1 | 105 | 21 | 4,356 | 1,537 | 0 |
| 005 | bridge U0→D1,2 | 126 | 7 | 7,008 | 3,685 | 126 |
| 005 | bridge U1→D2 | 28 | 7 | 1,452 | 312 | 0 |
| 005 | bridge U0,1→D2 | 203 | 21 | 9,912 | 4,910 | 203 |
| 086 | row L0 / L1 / L2, each | 1,472 | 16 | 13,152 | 19,844 | 0 |
| 086 | bridge U0→D1 | 120 | 24 | 5,040 | 1,774 | 0 |
| 086 | bridge U0→D1,2 | 144 | 8 | 8,112 | 4,258 | 144 |
| 086 | bridge U1→D2 | 32 | 8 | 1,680 | 360 | 0 |
| 086 | bridge U0,1→D2 | 232 | 24 | 11,472 | 5,672 | 232 |

The remaining original ops are also in the JSON: 005 has 235 source, 133 tail, and 19 detached ops; 086 has 256 source, 152 tail, and 20 detached. “Detached” means no recognized attention row is reachable in either direction, not that the op is dead or can be removed. Source and tail groups can be shared across multiple keys/layers; their original work is accounted for in the full per-label summary.

The bridge is structured but not a single serial shared block. In 005, U0→D1 contains 14 one-to-one projection-like singleton components and 7 one-to-many components; U0→D1,2 contains 7 one-to-many components. U0,1→D2 has 7 many-to-many components plus 14 many-to-one singleton components. The corresponding counts in 086 are 16, 8, 8, 8, and 16. One 005 U0,1→D2 component begins at original op 2678 with upstream row IDs `[0,7,14,21]`, representing two distinct layer keys, and downstream all 14 layer-2 rows. This is real cross-depth dependence and broad fanout. It does **not** prove those inputs must occupy a core simultaneously; reachability is weaker than liveness.

The validated bypass witness for 005, from layer-0 row sink 214 to layer-2 row node 2929 without entering a layer-1 row, is:

`214 → 1000000250 → 1276 → 1000001312 → 1278 → 1000001314 → 1280 → 1000001316 → 1281 → 1000001317 → 1294 → 1000001330 → 2678 → 1000002740 → 2691 → 1000002753 → 2839 → 1000002927 → 2844 → 1000002932 → 2846 → 1000002934 → 2847 → 1000002935 → 2908 → 1000002996 → 2929`.

Every consecutive pair was checked against an original `graph['edges']` pair. The analogous 086 chain is in `086.json`. A scheduler can use this partition to separate query-local bridge fragments from source/tail sharing and to identify bypass dependencies, but it still needs a proof for ownership of shared or joining bridge ops, capacity/spill legality, and full-path communication. This partition makes no submission plan and claims no zero-spill or score improvement.

Provenance: [FROZEN.md](FROZEN.md) fixes SHA-256 and the one-run budget. `partition.py` is the deterministic source; `005.json`, `086.json`, `summary.json`, `stdout.txt`, and `stderr.txt` are the original outputs. The process took 0.1656 s wall and 0.1645 s CPU on this machine; these are static analysis times, not solver times. Official scoring calls: zero.
