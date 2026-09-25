# R9F fixed full-500 proposal (not authorized/executed)

## Purpose and identity

This is a proposed final-round full run for one fixed, case-independent solver: commit `f6fd8153375a7fb64f9af2c8f36c35356fb7d878`, entrypoint `src.q3.fifth_core_final_solve`. It contains all 100 official cases × K1–K5 (500 unique cells) and a frozen rule: run the fresh Forest policy; only for K5 try the deterministic guarded contiguous fifth-core proposal; retain it only after a strict official P3 Makespan improvement and paired same-plan P2 nonworsening plus exact rational G nonworsening. Every cell uses a fresh child solver process. No case-number routing, history lookup, tuning, or retries are specified.

Files:

- `manifest-500-proposed.json`: canonical 500-cell coordinate map and worst-case reservations.
- `manifest-pilot-4-proposed.json`: 068/K5, 079/K5, 001/K1, 082/K4. The 068 cell exercises the new structural and paired-gate branch in a fresh solver process.
- `manifest-expansion-496-proposed.json`: the other 496 coordinates, suitable only as an explicit `--continue` stage after the pilot is reviewed.
- `identity-proposed.json`: fixed source-file SHA-256 values, official code/config identity, and all 100 case hashes from `docs/a/source-manifest.json` at the pinned commit.

All three manifests share one `run_id`, solver SHA/module, algorithm rule, budget, offline-cost statement, and runtime identity. The pilot and expansion job sets are disjoint and together equal the canonical 500. Use the pilot manifest first; only after its four records are complete, valid, and within budget should an operator explicitly pass the expansion manifest with `--continue` to the same output directory. A failed, timed-out, invalid, or ambiguous pilot ends the run; do not continue or retry. The runner retains the original batch deadline across continuation.

## Proposed budget

- 500 fresh solver processes, one worker, serial dispatch.
- K1–K4 each reserve at most 3 P3 calls and no P2. K5 each reserves at most 4 P3 plus 2 conditional paired P2. The worst-case full batch is 400×3 + 100×6 = **1,800** official E0 calls.
- Per cell 90 seconds; whole run 3,600 seconds, zero retries.
- Reservations are worst-case. The solver may use fewer calls; unused successful reservations are refunded by the runner only after a completed, validated receipt. A failure/unknown call is not refunded.
- The one-hour deadline is a proposed ceiling, not a claim that this run has been admitted or that it will complete. Resource scheduling and a fresh explicit coordinator admission are still required. No old budget is reused.

The runner executes jobs serially (`workers` is recorded as 1); the 3,600-second ceiling allows for a fresh process per cell and preserves a bounded final run. Solver child wall time is end-to-end for that process and includes online construction and internal scoring. Record outer per-cell wall, online evaluator wall/calls, and environment. A fresh process does not establish cold OS page cache or exclusive-host throughput; report host contention and cache state.

## Runner audit — verify before any dispatch

`src/q3/feedback_benchmark.py` does not independently verify the conditional P2 ledger or this selector's acceptance rule. The new `src/q3/fifth_core_full500_runner.py` wraps its serial dispatch, validates phase-specific E0 counts and all scored plan/result bytes, and checks the exact P2/P3 acceptance inequality before reporting a complete cell. It reuses an archived P2 result only when the new selected plan and graph/config/official identity match the fixed Forest control map. Pure mock tests pass; a fresh-score pilot is still required.

The generic validator's Forest-only candidate statuses cannot validate the new selector. The wrapper adds a selector-specific validator and rejects failed E0 ledger entries. These manifests remain proposals until that wrapper is committed, source/runner identities are frozen, and a distinct scoring window is granted. Do not change the solver source after freezing the manifest.

The solver only performs paired P2 calls when its K5 proposal strictly improves P3. For unchanged selected plans, the wrapper checks exact bytes and graph/config/official identity before attaching the existing Forest P2 original. For an accepted new plan, it checks the online P2 result of that exact plan. A completed 500-cell report must label new and reused P2 separately. A missing or mismatched P2 original is a failed paired audit, never filled from a different plan or historical best-cell combination.

## Pilot and resource caveats

The four-cell pilot exercises the new K5 paired-decision path and ordinary cells to test entrypoint integration and budget/receipt handling; it does not establish statistical significance or cover all graph structures. The fifth-core proposal has already passed pure policy tests and static construction on selected cases, but those do not establish official performance. No E0 calls were made while preparing this package. The prior static ceiling analysis also indicates the fifth-core family alone cannot lift the whole K5 mean above 5; any improvement must be measured across this fixed algorithm's complete eligible set, and a full500 result may still be negative.

This directory remains a proposal. The runner has only pure tests; no full500 evaluator/Task/Step call has been made. Do not dispatch until the wrapper and these manifests are committed and audited in a clean checkout, and the coordinator grants a fresh exclusive scoring window.
