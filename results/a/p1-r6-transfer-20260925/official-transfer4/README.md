# P1 R6 transfer4: four K5 mechanism-transfer cells

One bounded batch at fixed checkout `e74c00afed2fc1ab5ada75f7dda96bfd086fe4aa`, using the R6 branch-aid method whose `src/q1/branch_aid.py` bytes match source commit `db64a9375ffda535736ac54031a1184ee9f8f3d9`. This is a single-bridge mechanism transfer pilot, not the `src.q1.branch_refine` unified solver. Four cells, 4/500, were run in order 082, 075, 047, 005 (K5). The full 100×1–5 matrix remains unrun.

| Case | Baseline Makespan | Candidate Makespan | Extra DDR bytes | Spill bytes | Probe wall (s) | E0 wall (s) |
|---|---:|---:|---:|---:|---:|---:|
| 082 | 228535 | 198803 | 2709754 | 0 | 0.3473056250368245 | 0.6286194170243107 |
| 075 | 378832 | 379047 | 5457584 | 0 | 0.6103365000453778 | 1.1850848750327714 |
| 047 | 126217 | 111229 | 2336260 | 0 | 0.9028197909938172 | 2.311853874998633 |
| 005 | 42487 | 41072 | 1512506 | 0 | 0.3301016250043176 | 0.6080991249764338 |

The 075 degradation is retained as a negative result. Metrics are from the original E0 outputs. Probe and external E0 sampled process-group walls are reported separately. The outer detached controller exit code was not captured and remains unknown; the exact controller receipt/stdout report four cells classified. The raw result and trace JSON bytes are losslessly gzip-wrapped; raw candidate plan bytes define `identity.plan_sha256`. Frozen-v4 reference plans/results are preserved under each cell’s `references/`.

Calls: heavy constructor 4, branch constructor 4, E0 4, E1/E2/retry/new structure tests 0. Batch receipt, per-cell supervisor/probe original receipts, logs, stdout/stderr, launcher metadata, admission, and filtered host resource snapshot are retained and hashed in `MANIFEST.json`. Full desktop process listings are not included. CPU/GPU model and OS cache state were not recorded; exact dependency inventory and external controller return code are unknown.

The feed preflight checks format and available artifact bytes only; it does not rerun a solver or evaluator. This export does not claim official full-algorithm acceptance.
