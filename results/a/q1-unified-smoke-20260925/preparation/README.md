# Unified P1 smoke preparation

Status: **WAIT_ROOT_EXECUTE_AND_TAIL6_RELEASE**. No real graph, constructor, E0 or E1 has run for this batch.

Algorithm source: `48faef6f1386c3dc7d037674a38af29d533ba774`; Python must be the project `.venv` (3.12.13). Source modules copied byte-for-byte from that commit. The controller verifies the complete `src/q1` / `src/eval_exact` Python/JSON closure, lock/config/official input identities, and clean tracked runner before launch.

Order is 051, 044, 031, 008, all k5; single worker, maximum 4 solvers / 4 external E0 / 16 online E1, no retries. Cold solver limit 300 seconds, external E0 120 seconds, whole batch 1800 seconds, each including cleanup. Cleanup reserves up to two seconds. Group RSS is sampled every approximately 0.1 seconds; a sampled sum over 4 GiB stops the owned process group. This cannot detect a short spike between samples. `ps` sampler child CPU is included in receipt CPU; solver outer wall is the efficiency metric, external E0 wall is separate.

First failure stops subsequent cells, including a solver's internal score failure even if it emits a fallback plan. On interruption, unmatched score requests yield an E1 call interval and unknown exact count. Successful diagnostics must match flushed events; selected plan bytes must match the candidate SHA; the winning E1's makespan and complete movement dictionary must equal final official E0. A single distinct candidate may use zero E1. All raw logs, event lines, diagnostics, result, trace, PID/cleanup and RSS samples are retained.

The controller test uses four fake child processes (success, timeout, tiny RSS ceiling, nonzero), plus synthetic dictionaries for partial call accounting, full-movement mismatch and internal failure. It does not import the algorithm/evaluator or read real graph bytes. `controller-check.json` records this test, not an algorithm score.

After root authorizes the exact frozen runner/source/run tuple, the command is:

```sh
.venv/bin/python -B src/q1_benchmarks/unified_smoke.py run \
  --manifest results/a/q1-unified-smoke-20260925/preparation/manifest.json \
  --run-id ROOT_AUTHORIZED_RUN_ID \
  --authorization output/p1-unified-smoke-authorization.json
```

Authorization JSON must contain `gate: AUTHORIZED`, the full `runner_commit`, `source_commit`, `run_id`, and the root authorization message. No authorization file is created during preparation. No board export is part of this task.
