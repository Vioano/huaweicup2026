# P3 E2 integration decision, 2026-09-24

The E2 owner returned a read-only interface audit in[PR46 comment](https://github.com/huaweibei123/huaweicup2026/pull/46#issuecomment-5820881580), pointing to research pin`603b0741e21c449d3db652ebd67c94f2dc014cc9`. This document records that owner report and its implications; this P3 session has not loaded the native library or independently repeated the E2 tests.

Reported entry: `research.a.e2_search.SceneBEvaluator`, `read_config(..., problem=3)` and `evaluate_record(plan, full=False, **cfg)`. Native results are compact; full results use E0. Unsupported/error paths may use one automatic E0 fallback, which needs separate accounting. The reported differential evidence covers32 distinct plans on004/005, not our calendar/pipeline/witness plans or the full100×5 domain. Reported cold complete scoring speedups around1.55–1.58x are different from the much faster native replay kernel.

Do not substitute this call into`safe_solve.evaluate` blindly: that path preserves complete official results and treats every call as official E0. Native, fallback and final E0 counts, compact/full evidence and exceptions need distinct contracts. Our certified lower-bound pruning uses an exact E0 incumbent; an unproved fast score cannot safely replace it. E2-first, then one final E0 on its winner does not recover a better plan mistakenly discarded by E2.

The current complete calendar batch has861 onlineE0 evaluations over500solvers and reuses the winner result, without500 additional external confirmations. In the illustrative constant-per-call-cost model, replacing all861 calls with E2 plus500 final E0 calls only wins if cold E2 is faster by more than861/(861-500)=2.385x. This is not a measured whole-solver prediction: actual costs vary by graph/plan and must be time-weighted.

Decision: preserve E0 selection for the current bounded pipeline/witness experiments. Investigate exact byte-preserving result serialization reuse first. Reconsider E2 when the applicable domain/equivalence evidence or end-to-end cold cost changes; no new E2 benchmark or development was requested for this audit.

## 2026-09-25 所有者只读复核

E2 专项会话再次确认：P3 接口/适用域没有新证据，PR46 的固定HEAD仍为603b074；32计划差分、1.55–1.58倍冷完整评分及紧凑输出/fallback边界不变。P2 native全量不能外推至P3的forest/容量分段计划。此次未启动评分、开发或本机差分复测。

已完成forest500实际使用973次在线E0/500solver；同一等成本示意下，E2加500次最终E0的盈亏阈值为973/(973-500)≈2.057倍，不能沿用旧calendar的2.385倍。下一容量策略最多4次E0仅是上限，实际分布未测，不能用2000次上限代入宣称值得集成。仍先保留官方E0赢家选择与剪枝；若后续在该固定分布上证明关键字段/排序等价并计入冷启动、fallback、最终确认，再单独评估速度路线。
