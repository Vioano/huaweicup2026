# Frozen static layered bridge partition

Current published HEAD: `c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43`. Scope: only original 005 and 086, with the existing recognized row inventory in `layered-query-flow-audit-20260925/`. One worker, one script process, 60-second total SIGALRM wall limit, one analysis per case, 005 then 086; first exception stops, zero retries. No mutation of shared source or original inputs. Task, Step, construct, pipe_bound, E0/E1/E2 and all official/candidate scoring calls: zero. No plan is built. Actual token consumption is unavailable; delegation soft budget was 4500 tokens and 12 minutes.

Frozen SHA-256:

| File | SHA-256 |
| --- | --- |
| `partition.py` | `2ba574437560e23edd50e69ce393d57a2294f50e6c544ae5840ec7c4dd99eb3b` |
| `src/q3/query_flow.py` | `88aca80c6e5dac46e56a6894a165e40aab7e21ac68db66b6dac83539a1d2d2f0` |
| `src/q3/attention_rows.py` | `a4076188bda3037cdaa22686bf85d20051a3d8020e02d78d46db36adc5c10bb9` |
| `src/q3/construct.py` | `942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73` |
| official `stub_multicore_cut_and_schedule.py` | `0a3a3b79b5173b466fc05fc8d33b72d11d90b4df78995435853d91c632a35892` |
| official `case_005.json` | `c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f` |
| official `case_086.json` | `ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a` |
| existing audit `005.json` | `c1be132c2718c25f91fd6956c70f9200d71b801e83621be512eb3d4dc5d67f4c` |
| existing audit `086.json` | `fd659ff3346171c109152c7b795572e92d24b8c11baf29e0d16676c2739bf129` |

Static review: AST parsing passed. `Index` plus `_ports` and `_recognize` are only used for the frozen recognized row set; current row sink order must equal the existing audit. The official `_build_op_adjacency` is used solely to connect all original ops, including COPY, through original tensors, then `topo` orders them. For each op, forward/backward dynamic programming propagates **first row encountered** along every path; traversal stops at a row interior. Thus each non-row op has a deterministic nearest-upstream and nearest-downstream row signature, possibly empty or multirow. A disjoint role/band/relation label follows from that signature. Within a label, connected components are an inventory convenience only: original op IDs are never copied, removed, fused or submitted as grouped subgraphs. Full node-to-component and signatures, each component's IDs/count/work by original `pipe` and `cycles`, and role summaries are written. The script checks unique complete op coverage and exact conservation of original per-pipe cycle sums. One earlier-audit 0→2 bypass chain is checked edge-by-edge against the original graph.

Labels do not assert legal placement, zero spill, compute-time equality, or scoring gain. Multirow reachability may reflect a real join or a shared upstream source; a bridge's first-row signatures alone do not prove all data from those rows are jointly live. No CPU or wall runtime from this audit is a solver time.
