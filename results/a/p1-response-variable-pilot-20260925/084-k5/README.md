# Response-refine variable pilot: one cell

The frozen `response_refine.py` wrapper (`algorithm_id=q1-response-refine-experimental` as emitted by its CLI) ran once for P1 case 084, k=5 and selected `variable-packet-refinement`. Wrapper wall was 8.799125709s. It made one solver call and five online E1 calls (four baseline plus one refinement), with zero new E0, zero E2, and zero retries.

The final plan SHA bd30e21f6fb8a2c12e149902e90173acad7af377d9d06babe20619d56c6b1796 exactly matches the plan previously evaluated by E0. The existing result/trace/baseline are reused from the adjacent variable-packet package; no E0 ran during this pilot, so `evaluation_wall_seconds` is null here. Baseline selected makespan 399121; refined makespan 390425.

This is a single-cell pilot, not a new full500 score. See [feed](board-feed-084-k5.json), [public receipt](public-run.json), and [manifest](manifest.json). Raw receipt and diagnostics remain intact.
