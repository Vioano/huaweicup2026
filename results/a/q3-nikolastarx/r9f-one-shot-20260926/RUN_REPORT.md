# R9F 068/K5: one admitted official diagnostic

The frozen R9F contiguous fifth-core plan is **valid and faster in both scenes**, but it
does not pass the preregistered joint gate because its same-plan Cache gain falls.
This is a single-case mechanism result, not a fixed-algorithm score or a solver runtime.

| Exact 068/K5 plan | P3 with Cache (cycles) | P2 without Cache (cycles) | Same-plan `G=P2/P3` | Added DDR copy (bytes) | P3 byte hit rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Forest500 old control | 116,345 | 131,631 | 1.131385 | 4,341,362 | 0.213397 |
| R9F proposed plan | 97,971 | 98,913 | 1.009615 | 2,564,562 | 0.050489 |

P3 improves by 15.793%, P2 by 24.856%, and added DDR copy decreases by
1,776,800 bytes. The relative Cache gain falls by 0.121770. A lower hit rate
coexists with lower absolute runtime and lower traffic; therefore hit rate or
`G` alone does not explain absolute quality. The predeclared joint gate was
`M3_new < 116345`, `M2_new <= 131631`, and
`M2_new/M3_new >= 131631/116345`; its last condition is false.

The root began at `2026-09-25T18:55:09.628818Z` and ended at
`2026-09-25T18:55:51.031996Z`, 41.47 seconds of **diagnostic** wall time.
There was one P3 official call and one conditional P2 official call, each with
one Task and five of each Step1, Step2, prepareStep3, and Step3 simulation;
both completed with exit code 0. The P3 six-layer prepared guard passed:
5,351 original compute ops, 7,003 prepared ops, no spill-added copy,
five core UB peaks at or below 90,112 B, and the FIFO/cross-link union checks.
No retry or new online solver invocation occurred. The running parent and both
workers had exited at the cleanup readback. Memory pressure remained normal;
swap used did not grow. The runner records `solver_wall_seconds=null` by design.

Frozen diagnostic source is `4fc7e3d1fabf35b45376c993527bc79bd1bb8e1b`;
candidate plan SHA-256 is
`ee8364e769437cb226cbe95cde845c0bbea59b2fd4e84dc47806d517949b323b`.
The exact old control and admission hashes are in [README.md](README.md).
`run/` contains the unmodified compressed official results, captured prepared
Task/Step, claims, reservations, guard receipt, stdout/stderr, and the complete
call ledger. [RUN_MANIFEST.json](RUN_MANIFEST.json) hashes every original file.
Originals were copied byte-for-byte from the clean diagnostic checkout.

This result neither updates the old Forest500 full score nor approves a wider
official budget. The proposed fixed fifth-core selector on source `f6fd8153`
uses the stricter per-cell joint gate. Its full 100×1–5 benchmark remains
unrun; only that fixed run can establish a new overall score and cold solver wall.
