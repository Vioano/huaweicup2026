# Fixed-owner fcc coverage: remaining nine K5 cells (prepared only)

The original preregistered 12-cell selection is pinned by SHA `6060d2a281e963614eb0634dbf90454b3b7b52be73d0d6cc67287436e33d16b1`. This package dispatches only its remaining nine cells in original order: 019, 052, 061, 070, 074, 099, 076, 003, 084, all K5. The earlier fcc 006/089/097 results are historical evidence only; the older 15d 12-cell results are not fcc scores and are never merged into this producer's outcome.

A clean detached fcc source worktree is `/Users/nikolastar/.codex/worktrees/p2-fixed-owner-coverage9-20260925/huaweicup2026` (HEAD `fcc7fa2410edb5e2cd3868b1b7f2d7bce82b58a9`). The parent dev HEAD was left intact. Preflight pins and checks 81 tracked source/official-code files against the real fcc commit and working tree, all 71 Python modules, 20 official code/graph/config files, 51 E2 export files including native binary, E2 source manifest, selection original, single-core denominator, monitor and reused holdout helper, exact venv invocation path plus real binary SHA. The import-only child uses the actual Python invocation path; it does not read a graph or call an evaluator.

The one-worker adapter reuses the frozen holdout `cell`, `inspect_solver`, canonical plan/oracle originals, exact native-versus-independent-E0 metrics, and fixed monitor. Bounds: 9 cold solvers, at most 36 E2 API attempts, at most 9 independent E0 plus a one-call possible internal fallback reserve (total E0 at most 10), zero retry, 180 seconds per child, 900 seconds including preflight, 2 GiB observer-inclusive child RSS, VM pressure 1, swap growth at most 256 MiB, and 10 GiB free disk. The first failure, unknown count, fallback, resource fault, or metric mismatch stops new dispatch; unresolved calls remain marked and conservatively reserved. Actual native/fallback behavior cannot be guaranteed before running.

Two exact zero-E2 routes are allowed: the known `UnsupportedStructure('requires both fork and join')` signature, and `fixed_owner_duplicates_incumbent` with the frozen wrapper's complete no-request/one-unique-base-plan/constructed-count relationship and fixed-owner detail. Any unexpected, unknown, partial or differently labelled branch stops the batch. This precise adapter is covered by synthetic positive and field-mutation negative replay through the reused `inspect_solver`.

`gate-template.json` is pending and expired. Do not run until a coordinator issues a new admitted gate with exact runner/manifest/dependency hashes, future UTC expiry, and exact absolute output path. The output must not exist before starting. There is no auto-launch.

```sh
/Users/nikolastar/.codex/worktrees/p2-gap500-s59ee-20260925/huaweicup2026/.venv/bin/python -B /Users/nikolastar/.codex/worktrees/q2-continuation-s7d28/huaweicup2026/output/fixed-owner-coverage9-preparation-20260925/run.py run \
  --repo /Users/nikolastar/.codex/worktrees/p2-fixed-owner-coverage9-20260925/huaweicup2026 \
  --raw-root /Users/nikolastar/.codex/worktrees/q2-feedback-s8ee/huaweicup2026/data/raw/a/official \
  --e2-root /Users/nikolastar/.codex/worktrees/q2-feedback-s8ee/huaweicup2026/output/q2-e2-paircheck-603b-s8ee \
  --python /Users/nikolastar/.codex/worktrees/p2-gap500-s59ee-20260925/huaweicup2026/.venv/bin/python \
  --manifest /Users/nikolastar/.codex/worktrees/q2-continuation-s7d28/huaweicup2026/output/fixed-owner-coverage9-preparation-20260925/manifest.json \
  --gate /Users/nikolastar/.codex/worktrees/q2-continuation-s7d28/huaweicup2026/output/fixed-owner-coverage9-preparation-20260925/gate.json \
  --output /Users/nikolastar/.codex/worktrees/q2-continuation-s7d28/huaweicup2026/output/fixed-owner-coverage9-run-20260925
```

Offline checks only: `.../.venv/bin/python -B output/fixed-owner-coverage9-preparation-20260925/offline-test.py` and `run.py preflight` with the same repo/raw-root/e2-root/python/manifest arguments. No real solver or score call was made in preparation.
