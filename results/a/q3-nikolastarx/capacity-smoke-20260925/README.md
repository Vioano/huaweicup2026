# Capacity unified-entry smoke: frozen, not started

Frozen solver: `da1c9e86f9353ad4ca1bb3b8c720cef9b5043b49`, `src.q3.capacity_solve`.
`manifest.json` SHA-256 `6dc74e291e2caf20103737888397fac96dc26516581e30c252677155df7fda75`.
`resource_guard.py` SHA-256 `3cf66d153ef97f3f1122a4d738ca8cb2e817edeff28141e3584080e25288b90c`.
The manifest passed schema validation and the supervisor passed AST parsing; **zero solver, E0, P2, Task or Step3 calls have run**.

Two fresh CLI calls cover 044/5 (expected capacity proposal acceptance) and 001/5
(expected certified-bound pruning). Expected behavior is a hypothesis, not a passing
result. At most eight total online E0 calls, one worker, no retry, 60 seconds per
job and 180 seconds whole batch. No prior saved winner enters the solver.

The external supervisor requires two host observations with at least 1536 MiB
unused memory, no critical pressure or new swapout. It stops its own process tree
on less than 1024 MiB unused, critical pressure, a new swapout, sampled total tree
RSS above 512 MiB, monitoring failure or 190 seconds. Sampled RSS is not a hard
OS memory reservation or a continuously measured peak.

The shared resource coordinator `nikolastarx/s-a5bdb19389ee43d686b7976d3bcdf766`
held this run at approximately 00:55 UTC on 2026-09-25: its independent
free+speculative observation was about 0.561 GiB and swap usage 11.446/12 GiB.
That observation is not this supervisor's own top-unused preflight; neither
metric is silently substituted for the other. P1/P2 report no competing local
scoring, but that alone does not release the resource gate. No Colab runtime
was taken from P1 and no new runtime was started.

When admitted, use a clean worktree at the exact solver commit, copy this control
directory into the same relative result location, and run:

```sh
uv run --locked --no-sync python results/a/q3-nikolastarx/capacity-smoke-20260925/resource_guard.py --admission-reference 'ACTUAL PUBLIC SESSION AND WINDOW REFERENCE'
```

The supervisor and runner fail if source/manifest identity changes or the run
output already exists. Any later source edits require a separately frozen run;
this unstarted manifest is not permission to evaluate a different algorithm.
Results must report actual call ledger, complete solver wall, official metrics
and either success or failure. This smoke is not the required unified 100×5 batch.
