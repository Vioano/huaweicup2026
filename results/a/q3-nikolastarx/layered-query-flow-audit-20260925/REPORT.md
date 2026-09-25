# Original-edge layered attention audit

The frozen read-only script completed once for 005 and 086. It recognized 42 and 48 closed attention rows, respectively. Each row quotient is acyclic and has depths 0, 1, 2. There are no same-depth quotient edges. 005 has 14 rows and 7 distinct raw Q/K/V input keys at each depth; 086 has 16 rows and 8 keys at each depth. The key sets at different depths are disjoint (`keys_reused_across_depths` is empty for both). Each key is used by two rows at its depth. Thus R8's global key identification splits different attention depths into separate flows, and row outputs genuinely feed later rows. The failure at `query_flow.py:111` is explained by these original dependencies.

| Case | Rows by depth | Distinct keys by depth | First-downstream row edges 0→1 / 0→2 / 1→2 |
| --- | --- | --- | --- |
| 005 | 14 / 14 / 14 | 7 / 7 / 7 | 196 / 196 / 196 |
| 086 | 16 / 16 / 16 | 8 / 8 / 8 | 256 / 256 / 256 |

Every row at an earlier depth has an original-edge path to every row at each later depth before crossing another recognized row. The 0→2 paths show that a simple consecutive-layer-only handoff omits bypass dependencies. This is graph reachability, not a measured transfer count or minimum physical traffic.

One complete 005 path from depth-0 row sink 214 to depth-1 row node 1532, with every consecutive pair checked against `graph['edges']`:

`214 → 1000000250 → 1276 → 1000001312 → 1278 → 1000001314 → 1280 → 1000001316 → 1281 → 1000001317 → 1294 → 1000001330 → 1442 → 1000001504 → 1447 → 1000001509 → 1449 → 1000001511 → 1450 → 1000001512 → 1511 → 1000001573 → 1532`.

Intermediate compute op kinds on this path are MATMUL, ADD, MUL, ADD, ADD, SUB, DIV, MUL, ADD, MATMUL. These are concrete projection/interlayer processing nodes; the audit does not infer a named architecture or assign all bridge ops to FFN blocks. The per-edge JSON includes all original node-ID chains and intermediate op kinds for both graphs, including 0→2 bypass examples.

A guarded future “per-layer query affinity + fixed-core interlayer stream” construction would need to (1) prove rows and raw Q/K/V keys partition cleanly by acyclic depth as observed here; (2) account for every bridge node and both adjacent-layer and bypass dependencies, including shared/joining nodes, without assigning one op twice; (3) enforce physical tensor capacity and legal Task construction for the resulting owners; and (4) recompute remote crossings and compute/COPY service over the **whole** depth chain. Both graphs fail a stronger independent-stream guard requiring each downstream flow to have at most one upstream flow: their row quotient is complete across depth pairs. The R8 bound of at most two remote edges applies to its single-layer construction and cannot be inherited by a multi-layer path.

The next mathematical question is whether these dense, bypass-carrying bridge DAGs admit a compact factorization or shared-stage placement that keeps complete-path remote crossings bounded while preserving legal capacity. This audit supplies topology for that question; it neither constructs a submission nor establishes capacity, Makespan, or cache gains.

Provenance and limits: `FROZEN.md` fixes SHA-256 and the one-run budget. `005.json`, `086.json`, and `summary.json` are script outputs; `stdout.txt` and empty `stderr.txt` preserve execution. CPU time 0.111247 s, wall time 0.111319 s, official scoring calls zero. Timing covers only this local read-only script, not a solver.
