# Two-case official mechanism feedback

Source `87f677f8f16e31a71c071d49dd176d4420efb36d`, manifest-v2 material `5aea2d7ebbb625f1fe841a6c49b899782ea50bb3`. Raw originals: commit `7d11e18600474a15c51b1e94603bc1f0684943bf`, `results/a/q3-nikolastarx/shared-pipeline-probe-20260925/run`.

Two solvers, six online E0, no external re-evaluation or retry; Python3.14.5 on M5 Pro, one worker. Complete runner wall1.546s, solver walls0.686/0.535s. Plan/candidate/result hashes, selection and evaluation ledger were checked read-only. Fresh calendar incumbent is the winner of seed and gap, not necessarily the receipt entry called seed.

|Case/core|Fresh calendar M → pipeline M|Added COPY bytes|Spill bytes|Byte hit rate|
|---|---:|---:|---:|---:|
|044/5|83958 → 41205|3954560 → 1751296|0 → 1585152|0.046434 → 0.604754|
|046/5|88200 → 83050|3721600 → 1538048|0 → 1087488|0.174274 → 0.463055|

This is two seen mechanism cases, not a complete500 fixed-algorithm score. Do not splice these two rows into the calendar full500 result. Both improve M and total added COPY but worsen spill.

Read-only timeline/cache-event analysis locates the extra reload traffic on core2's shared original L1 inputs. In044 there are24 matching hits totalling1585152B; in046 there are15 hits totalling1069056B plus one18432B miss. Existing original COPY_IN backing permits Step2 reload without a new COPY_OUT. These records do not include full spill_records or allocation-trigger snapshots; the exact pressure at every eviction and a causal runtime contribution of Cache are not independently isolated.

The next mechanism to investigate is the shared-input live set and access order within a pipeline stage. Reducing spill alone is not a performance criterion. The pending Attention witness probe is a separate fixed source/case set and must retain its own evidence.
