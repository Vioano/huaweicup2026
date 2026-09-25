# Prepared structural-refine P1 matrix runner

`src/q1_benchmarks/s6607_structural_full500.py` is an **unexecuted research runner** for frozen solver `3a1b82b71ca1ff6689eb8e72f17d26c48b52073c` (`src.q1.structural_refine`). It leaves production `unified.py` unchanged. Review and commit the runner before use; its preflight rejects a runner file that differs from its HEAD and rejects drift in the frozen solver, official source manifest, config, archive, and direct helper sources.

From this worktree root, with the locked Python 3.12 environment and a fresh output directory:

```sh
PYTHONPATH=.:data/raw/a/official/code ../../.venv/bin/python -B src/q1_benchmarks/s6607_structural_full500.py --output-root results/a/<new-run-id> --cases 001,002 --cores 1,2 --workers 2
```

The complete 100×5 matrix requires the explicit `--full500` flag, with no partial selectors. Limits: up to 4 workers, one thread per process, 300 seconds per solver, 900 seconds per new official E0, 4500-second batch admission threshold, no retries, at most 500 solver starts, 4500 online E1 calls, 500 new E0 calls, and zero E2. The threshold limits new admissions and each subsequent process timeout; cleanup may extend total wall time. The first failed cell stops new dispatch; already started processes finish or are cleaned up, and all attempted and not-run cells retain receipts. A solver cell with unknown E1 dispatch count stops the batch and reports total E1 as unknown, never zero.

Every selected cell starts this solver afresh; prior solver time is never reused. The only possible E0 reuse source is the fixed v4 500-row feed at commit `0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297`. Reuse requires exact input/config/complete official code identity and plan bytes, verified old plan/result/run artifact hashes, fixed prior runner commit, successful independent official E0 process evidence, and matching result metrics. Missing evidence triggers a new E0. Reused evaluation wall is `null`, new E0 calls and reused results are counted separately. Online E1 scores never replace E0. Preflight checks all 100 fixed official single-core gzip artifacts at commit `6fcec11ccc472a1a652b21feb6fccf85a4555598` against the old feed's identical per-core baseline references. Those denominators remain separate from this solver's newly run k=1 plans; this runner does not export a board feed or compute speedups.

This preparation passed static syntax review and three ledger-only fixture tests. Existing 051/084 diagnostic artifacts were inspected read-only; they are not runs of this runner. No partial or full-matrix cell, constructor, E0, E1, or E2 was run for this runner. A partial pilot and a source/receipt review are required before full-matrix use. The P2 exclusive resource window has not been released, so do not start this batch yet.
