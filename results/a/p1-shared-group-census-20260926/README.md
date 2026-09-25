# P1 shared COPY_IN component census (static)

Source: `data/raw/a/official-cases.zip`, SHA-256 `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528` (100 official graphs). Run from the repository root:

```sh
python3 scripts/p1_shared_group_census.py --output results/a/p1-shared-group-census-20260926/census.json
python3 scripts/p1_shared_group_baseline_audit.py --output results/a/p1-shared-group-census-20260926/baseline-audit.json
```

The script verifies the ZIP hash, then reads each graph once. A component is a weakly connected set of non-COPY ops under direct op edges and tensor producer-to-consumer edges. A reused COPY_IN tensor is produced by exactly one COPY_IN op and consumed by compute ops in two or more components; *partial* means fewer than all compute components consume it. `consumer_groups` records exact sets of consumer component indices, with components numbered from zero in minimum-op-ID order.

| Measure | Cases / structure |
| --- | ---: |
| Graphs with cross-component reused COPY_IN | 74 / 100 |
| Graphs with partial reused COPY_IN | 56 / 100 |
| 011 | 16 components × 43 ops; 8 distinct four-component consumer groups × 22 tensors = 176 partial shared tensors |
| 027 | 16 components × 89 ops; 8 four-component groups × 45 tensors = 360 |
| 059 | 64 components × 43 ops; 16 eight-component groups × 22 tensors = 352 |
| 097 | 64 components × 103 ops; 16 eight-component groups × 52 tensors = 832 |

The per-case counts, component-size histograms and tensor bytes are in [`census.json`](census.json); exact consumer-component sets are retained for the four focus cases. They have regular consumer-group incidence and equal component sizes. This is a structural lead for studying shared-input grouping; equal sizes and consumer groups do **not** establish component DAG isomorphism, feasible Task partitioning, cache-capacity fit, or useful timing.

The second script reads the **already saved** K5 plans and `prior-result.json.gz` files from `p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500`; it does not regenerate them. For each shared tensor, it counts the distinct baseline Tasks containing a compute consumer. The count above one indicates a Task-boundary reread; `(count - 1) × tensor size` is a structural reread quantity, not a predicted time saving. Source paths and SHA-256 hashes, full Task-count distributions, and saved movement fields are in [`baseline-audit.json`](baseline-audit.json).

| Case | Shared tensors crossing baseline Task boundaries | Structural extra read | Saved spill COPY | Interpretation |
| --- | ---: | ---: | ---: | --- |
| 011 | 88 / 176 (50%) | 540,672 B | 0 B | Four active cores, one Task each; half the shared inputs already remain within one Task. |
| 027 | 300 / 360 (83.3%) | 2,727,936 B | 0 B | Six Tasks across five cores; a long tail Task remains. |
| 059 | 330 / 352 (93.8%) | 2,072,576 B | 0 B | Five active cores, one Task each; cleaner grouping study. |
| 097 | 832 / 832 (100%) | 17,039,360 B | 4,272,128 B | Largest boundary exposure, but capacity and spill interactions complicate attribution. |

Given those baselines, **059** is the cleanest first mechanism study; **097** has the largest structural exposure but requires explicit capacity/spill separation. **027** remains plausible with its extra Task and tail, while **011** has less ungrouped input left to address. This is a priority for checking mechanisms, not a performance ranking.

This census constructs and scores no plan. In particular, graph-visible reuse is not a valid two-key P1 submission or a Makespan claim. A future candidate would need complete eligible-op coverage, valid `node_to_subgraph` and `core_schedules`, the official combined data/core-order DAG and capacity checks, and separately authorized official evaluation. Solver, Task compiler, E0, E1 and E2 calls here: **zero**.
