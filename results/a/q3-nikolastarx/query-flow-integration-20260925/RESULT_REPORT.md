# Unified query-flow entry: fresh 071 / five-core validation

This is one fresh end-to-end unified solver selection on official 071/K5. It is not a new full500 benchmark. Frozen solver: `c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43`; delivery: `c1edb49324fd8ff45cabecec02cf051ab5ddd119`.

The final two-field plan has SHA-256 `b0ccb1c9d9e2f90ae6566ecaa725a0440c47d942401a3cdcb261d90eb0968136`. Its official P3 Makespan is **5785**, same-plan no-cache P2 is **7070**, and G is **1.2221261884**. The freshly constructed incumbent has P3 **7782** / P2 **8581**; all three frozen acceptance guards pass (P3 strictly lower, P2 no worse, G no worse). The selected plan matches the earlier isolated R8 mechanism result; this new run verifies automatic unified construction and selection.

All six online official calls completed once: four P3 candidates (8517, 7782, 7896, 5785) and two P2 guards (8581, 7070). Inner and outer ledgers agree; no retries and no external final evaluator call. This separately admitted six-call window is fully spent. The older R8 two-call window remains separate.

The supervisor reports complete/exit 0, T0 2026-09-25T13:22:24.736912Z and T1 13:22:25.802693Z. Its inclusive wall is **1.1744653750 s**, including monitoring and cleanup. Runner-entry wall is **0.5635766250 s** and excludes OS process startup; the internal 0.4906 s to evidence is not full solver time. Online evaluation time is already included, not added again. This was a fresh process, with no evidence of cold OS caches or exclusive performance benchmarking.

P3 scheduled movement is 393630 B, added movement 272184 B, spill 0 B; byte cache hits/misses are 90264 / 212646 (hit rate 0.2979895). These traffic categories must not be summed. P2 has the same reported movement and no cache statistics.

The three resource samples have normal pressure, no conflicting scorer, and zero swap-used growth. One-second sampling cannot prove peak RSS stayed under a hard bound. The final owned group is empty; root and coordinator independently observed no remaining PID66301. The coordinator readback released the shared scoring slot.

## Provenance and known metadata discrepancy

Run/control originals are in `run/` and `integration-control/`. The authorized manifest SHA is `b93b1aee59d876d4c93a20f72ed99af47cc0876d4612b114cef0b09f1100fe78`; external admission SHA is `3787f8f2d73fb0397bdf1df6c617711ebb46d77c56e82c5b76967b7edac53f38`. The manifest and receipt retain the old `proposal_pending_scheduler_approval` resource-policy label because admission allowed only the authorization/status fields to change. Actual explicit admission and `execution_authorized=true` were checked before launch. This text discrepancy is disclosed; original evidence is not edited.

Execution was delegated to Luna/medium with a soft 2500-token/12-minute budget; actual token usage is unavailable. Export is a separate zero-evaluation task. Scientific full500 acceptance and board ingestion remain separate from this local successful run.
