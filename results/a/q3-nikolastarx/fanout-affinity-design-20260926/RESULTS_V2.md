# Exact COPY-byte tie-break: one-shot static result

[`FREEZE_V2.md`](FREEZE_V2.md) fixed source/input hashes, parameters, candidate key, and stop rule before the run. [`gap_dag_affinity.py`](gap_dag_affinity.py) is the isolated constructor; [`run_static_v2.py`](run_static_v2.py) produced [`static_v2_results.json`](static_v2_results.json) and the six saved plans. Command: `PYTHONDONTWRITEBYTECODE=1 python3 results/a/q3-nikolastarx/fanout-affinity-design-20260926/run_static_v2.py`. It exited 0 after one old and one affinity construction for each case in frozen order. There was no exception, retry, parameter adjustment, official evaluator, Task/Step, solver, Pro, or network call.

| Case | Plan changed? | Old → affinity modeled finish (cycles) | Old → affinity cross-core tensor pairs | Old → affinity cross-link bytes | Old → affinity nominal inserted COPY bytes |
|---|---|---:|---:|---:|---:|
| 010 | No | 12,019 → 12,019 | 140 → 140 | 305,670 → 305,670 | 611,340 → 611,340 |
| 015 | Yes | 20,989 → 20,989 | 238 → 238 | 424,224 → 424,224 | 848,448 → 848,448 |
| 065 | No | 6,902 → 6,902 | 97 → 97 | 110,676 → 110,676 | 221,352 → 221,352 |

The 015 change moves seven operations between cores 3 and 4 (304–306 and 324 from 3→4; 310–312 from 4→3). Its `node_to_subgraph` mapping is unchanged. All six plans passed `derive_multicore_plan`; a separate static check verified exact non-COPY coverage, one operation per subgraph, and all contracted same-core dependency orders (010: 667 operations/700 dependencies; 015: 1,013/1,063; 065: 704/741). There were no direct op→op cross pairs in these plans. The full plan hashes and measurements are in the JSON record.

The low-risk tie-break is **not completely inert**: it changes 015's placement. But it produced no reduction in the measured static tensor-pair or byte proxy on any of the three frozen graphs, and no reduction in modeled finish. This one-shot result gives no positive evidence for advancing this exact tie-break to official P3 scoring. It does not falsify the underlying fanout accounting gap, and equal static totals do not prove equal cache, spill, capacity, or official Makespan behavior. No claim of official improvement or full-500 achievement follows.
