# Guarded component route, P2

`src/q2_nikolastarx/adaptive_guarded.py` is a standalone wrapper for
`adaptive_semantic.build`. It injects `guarded_component.make_component_builder`
and only requests E2 scores when the component pressure guard constructs a
distinct DAG candidate. The existing word, tree, and vector repair routes keep
their structural behavior. A returned E2 score compares the component builder's
two complete plans; it is **not** a certificate for any subsequent semantic
repair or the final P2 plan.

Invocation from the repository root, with an isolated 51-file E2 export at
the fixed commit `603b0741e21c449d3db652ebd67c94f2dc014cc9` (prepare it using
`src/q2_nikolastarx/e2_plan_pairs.py prepare` and the pinned probe manifest):

```sh
.venv/bin/python -m src.q2_nikolastarx.adaptive_guarded PATH/graph.json \
  --cores 4 --config data/raw/a/official/data/config.txt \
  --e2-root PATH/TO/PINNED/E2 --output PATH/plan.json \
  --evidence PATH/new-evidence-directory --wall 240
```

The output has exactly `node_to_subgraph` and `core_schedules`. The evidence
directory must be new. `solver.json` records input/config hashes, selected
route detail, plan hash, elapsed wall time, and E2 request ledger. When scoring
is needed, it also records the source pin, source-check time, and each attempt's
plan hash, full returned record, and wall time. With zero scoring requests,
`source_checked=false`; the E2 root is not opened. `internal_wall_seconds`
starts in this Python `main` after module startup/imports. It includes input
load, index construction, any source verification, E2 subprocess preparation
and scoring, structural validation, and plan writing. An external runner's
process wall time is authoritative for end-to-end timing because it also
includes Python startup/imports.
At most two public E2 `evaluate_record(..., full=False)` requests are made per
run. Each request may enter E0 through the E2 fallback. The ledger records
attempted calls, confirmed native returns and E0 fallbacks, plus one possible
fallback for an in-flight or failed request. There is no retry.
`calls.E0` conservatively includes that possible fallback until the request
returns; `calls.E0_fallback` counts only confirmed fallback records. An
uncertain in-flight request blocks any further scoring in that process.

The E2 worker runs in a fresh Python process with its own import path because
both repositories contain a top-level `src` namespace. Its source files are
checked byte for byte against the Git commit and probe manifest before scoring;
the native binary is checked against the probe's recorded SHA-256. Unexpected
executable/source files in the foreign E2 and `src/eval_exact` trees are
rejected. The verified native binary is restricted to macOS arm64. The worker
runs with bytecode generation disabled. Only
`route=native`, `status=ok`, `problem=2` and valid nonnegative integer score
fields can affect selection. Any fallback, malformed result, or evaluator
exception preserves the component baseline. The final output receives only
the official structural plan check, which does not prove P2 execution
feasibility. A separate unchanged E0 final evaluation is required before
claiming official quality. This wrapper has not been run on a real graph or E2
evaluator in this integration step.
