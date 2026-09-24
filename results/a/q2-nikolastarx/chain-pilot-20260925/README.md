# Six fixed chain-packet candidates: bounded pilot

This is an execution package for six existing five-core plans (003, 005, 056,
068, 086, 088). The plans are loaded byte-for-byte from commit
`ee4fe0282ca2ff5d73bb23d54b1c213909e1401c`; their constructor source was
`47baf7f89948aa0a1ea2038c823e60513c78f160`. The existing baseline feed and
official truth are pinned to `60afc38b327680fbda0ff10182e3e05a01edd72d`.
`manifest.json` carries the individual plan, graph, truth, config, source and E2
identities. The runner reconstructs no plans and makes no online choice.

The least expensive safe execution is the existing isolated E2 export at
`output/q2-e2-paircheck-603b-s8ee` plus the new thin pilot runner. Before any
evaluation, preflight verifies every exported E2 source against its Git object,
the native binary against its recorded digest, the official graph/config/code,
all six candidate plan blobs, the baseline feed, and six baseline truth results.
It performs no solver, Step1/2/3, E0, E1 or E2 call.

```sh
python3 -m src.q2_nikolastarx.chain_pilot preflight \
  --manifest results/a/q2-nikolastarx/chain-pilot-20260925/manifest.json \
  --e2-root output/q2-e2-paircheck-603b-s8ee
```

The future `run` mode requires a **full committed runner SHA** containing the
unchanged runner and manifest, and an output directory that does not exist.
This package has only been preflighted; no evaluation has been dispatched.
When scheduled within the reserved resource window, run one batch with
`--runner-commit <full SHA> --output <new directory>`. It processes cases in
manifest order, one monitored worker at a time. Each worker requests public
`SceneBEvaluator.evaluate_record(..., full=False)` once, then invokes the
unchanged official P2 CLI independently once. It compares Makespan, all five
movement fields and `cross_task_traffic`; it also records the comparison with
the frozen baseline. A fallback, error, timeout, RSS breach, process survivor
or E2/E0 mismatch stops the batch immediately. There are no retries or resumes.

Limits: at most six E2 requests, six possible E0 fallbacks, six independent E0
calls, one worker, 120 seconds per case, 600 seconds from batch preflight start,
and 4 GiB combined observed process-tree RSS. An in-flight request may have
already entered fallback; its ledger records that uncertainty before any call.
The outer process monitor saves child-tree receipts and cleans up descendants.
Each case has its own immutable output directory and call ledger. These are
fixed-candidate evaluations, not a 100×1–5-core result for a single frozen
solver. Constructor time was not recorded in the earlier preflight and is
reported as unavailable; evaluation and pilot preflight wall times are separate.

Frozen runner, manifest and monitor: `9e84fc880aaf48129ef3c0ab5414c52b48ba7a29`.
Root preflight with that exact SHA passed, 6 cases and 0 calls. The resource
owner subsequently prioritized a P3 full500 batch; this P2 run remains pending
explicit window release. No replacement run or larger budget was started.
