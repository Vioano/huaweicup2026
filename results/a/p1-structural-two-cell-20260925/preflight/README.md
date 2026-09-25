# Structural two-cell offline package

Preparation only: no solver, E1/E0, or VM was run. Fixed solver `3a1b82b71ca1ff6689eb8e72f17d26c48b52073c`, cases 016/024 at K5, graph SHAs are recorded in `bundle-manifest.json`. The small deterministic bundle contains `src/q1`, `src/eval_exact`, `bounded_probe_e0.py`, official evaluator/config/source manifest, author dependency `p1_phase_cut.py`, locked Python files, the entrypoint, and only those two graph JSON files; it excludes `.git` and the 100-case archive.

The entrypoint reserves at most 2 solver calls, 18 E1 calls (9 per graph upper bound), 2 E0 calls, zero E2/retries, one worker. It stops at first failure, records unresolved E1 as unknown with a 9-call reservation, and will not dispatch E0 unless diagnostics, plan identity, and E1 ledger validate. Per solver/E0 ceilings are 180/120 seconds. Controller session is single-use; watchdog stops at 690 seconds, VM wall cutoff 720 seconds, remote setup ceiling 540 seconds, with host exec capped at 560 seconds and a 100-second stop/download reserve. The 540-second remote cap is aggregate: if earlier setup/stages consume time, later stages are refused rather than exceeding it.

After coordinator resource admission only, copy the five covered files plus `artifact-manifest.json` into a new empty runtime directory; use the locked project Python. Do not execute from this tracked preflight directory. Host command:

```sh
python -B controller.py --execute --cli "$HOME/.local/bin/colab" --artifact-manifest-sha256 395f8e4e73c84f6ccc54a076ca50c0b4008e182d080ff84443d70c3ead0261c8
```

The pin covers controller, evidence verifier, remote setup, source bundle and bundle manifest. Fake-only contract tests and unpacked `--help`/import checks do not constitute solver or scoring evidence.

Startup cleanup also covers a launched child whose process identity cannot be read: kill/wait uses the owned Popen child, never an unverified process group, then reaps adopted descendants and archives the failure evidence.
