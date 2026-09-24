# P3 E2 integration decision, 2026-09-24

The E2 owner returned a read-only interface audit in[PR46 comment](https://github.com/huaweibei123/huaweicup2026/pull/46#issuecomment-5820881580), pointing to research pin`603b0741e21c449d3db652ebd67c94f2dc014cc9`. This document records that owner report and its implications; this P3 session has not loaded the native library or independently repeated the E2 tests.

Reported entry: `research.a.e2_search.SceneBEvaluator`, `read_config(..., problem=3)` and `evaluate_record(plan, full=False, **cfg)`. Native results are compact; full results use E0. Unsupported/error paths may use one automatic E0 fallback, which needs separate accounting. The reported differential evidence covers32 distinct plans on004/005, not our calendar/pipeline/witness plans or the full100×5 domain. Reported cold complete scoring speedups around1.55–1.58x are different from the much faster native replay kernel.

Do not substitute this call into`safe_solve.evaluate` blindly: that path preserves complete official results and treats every call as official E0. Native, fallback and final E0 counts, compact/full evidence and exceptions need distinct contracts. Our certified lower-bound pruning uses an exact E0 incumbent; an unproved fast score cannot safely replace it. E2-first, then one final E0 on its winner does not recover a better plan mistakenly discarded by E2.

The current complete calendar batch has861 onlineE0 evaluations over500solvers and reuses the winner result, without500 additional external confirmations. In the illustrative constant-per-call-cost model, replacing all861 calls with E2 plus500 final E0 calls only wins if cold E2 is faster by more than861/(861-500)=2.385x. This is not a measured whole-solver prediction: actual costs vary by graph/plan and must be time-weighted.

Decision: preserve E0 selection for the current bounded pipeline/witness experiments. Investigate exact byte-preserving result serialization reuse first. Reconsider E2 when the applicable domain/equivalence evidence or end-to-end cold cost changes; no new E2 benchmark or development was requested for this audit.
