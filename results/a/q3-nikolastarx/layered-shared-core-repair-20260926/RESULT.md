# Single shared-component relocation: static result

The frozen rule selected the sole baseline violation: core 0 UB peaked at 221,208 B at local bucket 145, op 4551, exceeding 131,072 B by 90,136 B. It moved all 15 shared components assigned to core 0 (706 compute ops, 504 M cycles and 36,357 V cycles) to the empty fifth core. Private track ownership was unchanged.

**The capacity failure moved intact.** Core 4 now peaks at the same 221,208 B, same local bucket 145 and op 4551, again 90,136 B over UB. Core 0's M/V work changes from 66,600/64,962 to 66,096/28,605 cycles; core 4 changes from 0/0 to 504/36,357. This is evidence that moving all of core 0's shared components as one block does not narrow their local live-tensor frontier. It does not prove that a different, separately justified decomposition or actual Step2 behavior has the same peak.

The static compute/FIFO `Ldelta` changes 119,073→93,450 cycles and whole-path envelope `Ldelta` 131,562→111,433; the whole-path remote-edge count remains 7 and its `layers+1` guard passes. These are conditional graph/FIFO calculations, not official Makespan. Source-rule remote links increase 468→474, cross-core payload 393,984→395,136 B, and predicted task COPY bytes without spill 5,329,284→5,331,588 B. The candidate still fails the no-spill frontier guard, so it is not a complete R9 static certificate.

One original graph, one fixed move, zero retries. No `construct_layered`, `derive_multicore_plan`, Task, Step, solver, or evaluator calls. [result.json](result.json) contains before/after peaks, loads, path witnesses and source-rule traffic. Production source was unchanged.
