# Archived 003/k2 hyperrefine probe

One process runs `gap_hyperrefine.refine` once on the saved static 003/k2 seed
placement, with `region_width=16`. The seed is reused from
`../pro-r04-review-20260925/static-003-k2/seed-plan.json.gz`; this experiment
does not include its construction time. Input graph and config are passed as a
directory argument. The script checks their known SHA-256 digests, the seed
compressed and decoded digests, structural validity, and the seed's independently
counted 6,351,422 pre-Step2 original COPY bytes before refinement.

Budget: one worker, one refinement, 30 seconds hard child wall limit, zero
retries, zero E0/E1/E2 calls. No official Makespan or capacity claim follows
from a byte decrease. Shared-machine timing is not an exclusive performance
measurement. The script records a complete compressed output plan and receipts
in a fresh output directory, even when there is no byte gain.

Example from the repository root (paths supplied by the caller):

```sh
python3 results/a/q2-nikolastarx/hyperrefine-probe-20260925/probe.py \
  --source-commit "$(git rev-parse HEAD)" \
  --raw-root /path/to/official/data \
  --seed results/a/q2-nikolastarx/pro-r04-review-20260925/static-003-k2/seed-plan.json.gz \
  --output results/a/q2-nikolastarx/hyperrefine-probe-20260925/run-003-k2
```

2026-09-24 UTC attempt: the first invocation used a short SHA and failed the
outer exact-HEAD preflight before creating a child. The subsequent invocation
created one child; it failed during import with `ModuleNotFoundError` for
`evaluation_validation` before calling `refine`. See `run-003-k2/process.json`
and `stderr.txt`. Actual refinement and evaluator calls were zero, and no plan
or byte result exists. The import order is corrected in the script after that
attempt. The frozen zero-retry budget was respected; no further child was run
under that batch. A separately authorized `run-003-k2-v2` uses the corrected
script with the same one-worker, one-refinement, 30-second, zero-retry budget.

The authorized `run-003-k2-v2` entered `refine` once and failed in its first
narrow region: `load_guarded_cut` received the global chain-work mapping rather
than work restricted to that region (`ValueError: work must have one record per
unit`). See its `process.json` and `stderr.txt`. This is an adapter defect
exposed by the 9,903-chain input, not an algorithm result. No output plan or
after-byte count was produced, and no evaluator was called. This batch was not
retried; a future probe requires an independently reviewed source fix and new
authorization.
