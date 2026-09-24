# Three-cell hyperrefine and fixed-core retime pilot

Fixed coordinates: 003/k5, 043/k5, 056/k5, in that order. Every cell runs the
same cold candidate pipeline: `gap_candidate.build` once, check exact equality
with its saved old production plan, `gap_hyperrefine.refine(region_width=16)`
once, then `gap_retime.retime` once only if exact pre-Step2 original COPY bytes
strictly decrease. Old plans and E0 results are identity/comparison evidence;
they do not generate the candidate. The selected complete plan gets one public
native E2 request. An independent official E0 runs only if native Makespan is
strictly lower than the old same-cell E0. A native fallback, unknown outcome,
failure, timeout, resource breach, identity mismatch or E0 mismatch stops the
remaining batch without retry.

Limits: one worker; at most 3 E2 API calls, 3 independent E0 calls, no E1;
at most 60 seconds for each cold candidate plus E2, 60 seconds for each E0,
360 seconds total, 4 GiB observed process-tree RSS, zero retries. The pilot is
three cells of a new method. Its timing includes graph read, all candidate
construction stages, native E2 and plan write, but excludes comparison with
the old `adaptive_budget` route. It is not a full production solver or a
100×1–5 score. Static Pipe work/lag is not an official Makespan bound.

Inputs are passed at run time; the script contains no machine-specific paths:

```sh
python3 results/a/q2-nikolastarx/hyperretime-pilot-20260925/pilot.py \
  --runner-commit "$(git rev-parse HEAD)" \
  --raw-root /path/to/official/data \
  --old-run /path/to/old-gap-full500-run \
  --e2-root /path/to/isolated-603b-export \
  --output results/a/q2-nikolastarx/hyperretime-pilot-20260925/run
```

The runner checks the fixed script and constructor bytes against its full
commit, official code/data/config against `docs/a/source-manifest.json`, E2
source and native binary against `check_e2_source`, and old per-cell plan/E0
identity. Artifacts include gzip-compressed plans and native/E0 originals;
compression roundtrip and raw/compressed hashes are recorded. The original
uncompressed E0 files remain alongside their archives for direct inspection.
