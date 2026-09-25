# Root readback: convex warmup diagnostic

2026-09-25 UTC. The current accepted full500 solver and its K5 mean remain unchanged (311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1, 4.7576166788448955; same-plan mean G 1.082917172693062). This packet is one case005/K5 mechanism candidate, not a solver release.

The 201-op cut is rejected by an actual 71-edge data/FIFO/cross-core cycle with no old memory-reuse edge required. The stronger raw-compute plus complete per-core-word quotient selects the earliest safe left boundary 9, ending at rank202: 194 compute ops. Acyclicity of that stronger envelope is a sufficient structural screen, not a performance bound or a necessary property of all valid plans.

The 194-op stable bucket sort reuses the sole official Step1 raw sequence; exact old and 201-op sequence replays precede the new sequence. The necessary graph contains all5135 local ops,17083 unique arcs and381 cross links. It is acyclic, with local closed-interval peaks19008 L1/21844 UB bytes. Independent Sol review found no missing pipe or cross-copy edge. New core0 Step3 memory edges and any Step2 rewrites remain unobserved; formal legality and time still need the official pipeline.

Target COPY1000004471 of key1000000048 retains MTE2 ordinal46, while its managed-allocation ordinal changes248 to244. All four pipe words change. This justifies one falsifiable issue-time test; it does not predict Makespan improvement or prove earlier cache insertion. No arbitrary grid/search or additional candidate is admitted.

The multi-op guard now uses full local Task tensor intervals, checks same-bucket memory arcs and the complete joined graph, and reports crossing count without falsely claiming the singleton layers+1 bound. The first toy attempt failed due to fixture expectations; the subsequent recovery failed before import because PYTHONPATH was absent. Both originals remain. The separately frozen import-path recovery passed five corrected toys and default/multi readback of archived singleton R9 bytes; no new official call. The probe control/hash and five decision cases passed once. Mock/test evidence cannot substitute for the new actual prepared Task.

Proposed cap: one P3 E0, one same-plan P2 only after all guards pass and M3<24522; joint improvement requires M2<=29026 and G>=max(29026/24522,37327/30642). Otherwise save the negative result. One worker,90s per phase,600s total,first exception stop,zero retries. Diagnostic wall is not cold solver wall. New resource admission is required; old Step1/R9 windows are closed.

A single frozen pure lower-bound check gives23682 cycles for the exact new word (optimistic copy durations, actualFIFO/data/crosslink dependencies, no new preparation). At fixed M2<=29026 this leaves at mostG=29026/23682≈1.2257; restoring ForestG requiresM3<=23827 if M2 remains29026. This is a narrow mechanism test, not the main route to K5 mean>5.
