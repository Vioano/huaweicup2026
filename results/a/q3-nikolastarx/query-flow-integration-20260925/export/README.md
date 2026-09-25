# Unified 071/K5 board export

This feed contains two paired records: the final P3 result and the same-plan no-cache P2 guard. Both refer to one unified solver invocation, run ID `q3-query-flow-unified-071-k5-20260925T132224Z`; do not sum their repeated shared run-level wall time. The single invocation is counted once on P3, while P2 records the two P2 E0 guard calls. The full original outer ledger records all six online E0 calls (four P3, two P2), no retries.

The solver source is frozen at `c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43`; the actual delivery/runner source is `c1edb49324fd8ff45cabecec02cf051ab5ddd119`. These are different identities and are both retained. Solver wall is the external supervisor's complete T0–T1 window, 1.1744653750211 seconds, including pre-child sampling and post-child terminal checks/cleanup. Child T0/T1 are lifecycle markers inside this window; their difference is not the reported solver wall. The `run` artifact points to `integration-control/receipt.json`, which records the 1.1744653750211-second value; `run/outer_receipt.json` remains a diagnostic reference with its path and SHA in each feed record. The runner-entry diagnostic is 0.5635766250197776 seconds. All six E0 calls were online and already included in the solver window; do not add the P2/P3 evaluation durations to it. This was not a proven OS-cold-cache measurement.

Original plan, compressed results, run/outer receipts, E0 ledger, supervisor samples, manifest, and single-core baseline remain at the paths and byte hashes embedded in `feed.json`. The baseline is the frozen official single-core A result (M=18919). The manifest's `resource_policy_proposal="proposal_pending_scheduler_approval"` label remains as originally recorded despite the separate explicit admission and completed receipt; it is disclosed in both feed records, and no original was rewritten.

The board protocol preflight was run without any solver or evaluator execution:

```sh
python3 src/benchmark_board/protocol.py /Users/nikolastar/Projects/huaweicup2026/.worktrees/q3-core-nikolastarx/results/a/q3-nikolastarx/query-flow-integration-20260925/export/feed.json --repo /Users/nikolastar/Projects/huaweicup2026/.worktrees/q3-core-nikolastarx --submission
```

Captured output is in `preflight.stdout.txt`: `valid=true`, `eligible=2`, `records=2`, format and available-byte checks only. `--repo` points at the current worktree because the integration originals are uncommitted there and are absent from the main checkout; the result does not certify a fixed delivery commit or scientific acceptance. The first schema preflight failure is retained in `preflight-initial.stdout.txt`; the missing dependency-environment reason was added to the generator, not to any original data.

The feed is a localized 071/K5 report, not a full algorithm or full-500 result, not independent replay, and not algorithm acceptance. One-second resource sampling is not a hard peak RSS guarantee. Cold solver time and cold OS-cache state are not available.
