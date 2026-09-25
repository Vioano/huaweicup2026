# R9 layered-flow one-shot diagnostic: prepared, not dispatched

This runner is a diagnostic of one fixed `case_005` / five-core plan. It is not a solver run or a timing claim for plan construction. No official evaluator, Task, Step, constructor, or pipe-bound invocation occurred during preparation.

## Frozen implementation and pure check

- Entrypoint: `src/q3/layered_query_flow_probe.py`, SHA-256 `c431b3ff64c8a9a24f862a7b0e6f3ea5ef498751850536361df58d27aecc7724`.
- Pure tests: `tests/test_q3_layered_query_flow_probe.py`, SHA-256 `a1b190b129d57e700ada78e33fa6a884dc94b3ace23bd152df6b37a4b6f1ddeb`.
- Guard interface: `check_layered_prepared(graph, plan, captured, layers=3)` from `src/q3/layered_prepared_guard.py`. Its current working-tree SHA-256 at preparation was `f4ff0045917d3868663e98a1ea6ca08145874494fbb30474e047e523be4e3ec8`; the dispatch-time pinned HEAD and clean-source check will govern its final bytes.
- Command run: `python3 -m unittest tests.test_q3_layered_query_flow_probe -q`; five pure tests passed. `pytest` was unavailable in system and project Python, so the test module uses standard-library `unittest`. One assertion in the first draft incorrectly treated a lower denominator as lowering the ratio; it was corrected before this frozen record. No evaluator was run.

The old-control file is `control/control.json`, SHA-256 `06ed2d4590fa6f30aebd930ab18708b27c716979349d12983281eea697457658`. The pure preflight read its bundled plan/P3/P2 originals and verified their byte hashes and same-plan P2 pair evidence: old M3=30642 cycles, old M2=37327 cycles. Its recorded source-feed and source paths do not exist in this worktree, so those external archived files were **not** independently reopened here; their provenance remains the control producer's record. The bundled three originals were reopened. The runner rejects any control/input/config/official-code hash mismatch.

## Fixed dispatch window awaiting root

Dispatch remains disabled until root provides all fixed values, commits the runner and guard, and confirms external supervisor ownership of the process group:

| Field | Required value |
| --- | --- |
| Plan directory | Existing directory under `results/a/q3-nikolastarx/` containing only the selected `case_005_multicore_res.json` plan for this run |
| Plan SHA-256 | Full hash of that exact plan file |
| Output directory | New, absent directory under `results/a/q3-nikolastarx/` |
| Source | Pinned 40-character HEAD with clean tracked files and no untracked `src/*.py` |
| Admission | Existing root-provided admission file path and full SHA-256 |
| Control | `results/a/q3-nikolastarx/layered-one-shot-20260925/control/control.json` and the hash above |

Command shape after those fields are frozen:

```sh
python3 -B -m src.q3.layered_query_flow_probe PLAN_DIRECTORY NEW_OUTPUT_DIRECTORY \
  --source PINNED_HEAD --plan-sha256 PLAN_SHA256 \
  --admission-file ADMISSION_FILE --admission-sha256 ADMISSION_SHA256 \
  --control CONTROL_FILE --control-sha256 CONTROL_SHA256
```

`verify_source` checks HEAD, tracked cleanliness, untracked Python source, official manifest inputs/config/code, all `src/q3/*.py`, and `uv.lock` before any reservation. The parent hashes admission and control before creating output. Each child rechecks source, plan and admission bytes against its reservation. A missing dependency or mismatched hash aborts; it is not a reason to retry or substitute another file.

## Bound and evidence contract

One sequential worker at a time; maximum one P3 and, only if prepared guard passes **and** candidate M3 < 30642, one P2. Thus maximum two E0 evaluations, zero retries, 90 seconds per phase and 600 seconds total. Each child remains in the external supervisor's process group; timeout terminates or kills only its own `Popen` child, never the parent group. Every phase gets reservation, exclusive claim, worker receipt, raw stdout/stderr and full gzip result. P3 captures the official `Task3` return and Step2 returns, writes `prepared.json.gz` before calling the guard, and saves `PreparedGuardError.as_dict()` on failure. First error stops the sequence.

A candidate is marked accepted only when guard passes, candidate M3 is strictly lower, candidate M2 is no higher, and candidate M2/M3 is no lower than old M2/M3, compared as exact rational numbers. A completed but rejected diagnostic is retained as such. `run.json` records identities, invocation budget, decisions and diagnostic wall time; `solver_wall_seconds` remains null because construction is not timed. Guard `step3_local_memory_peaks` refer to saved prepared Step3 local state. Official `memory_peak_by_core` copies those values and is not an independently observed multi-core runtime memory peak. No no-spill proof or general-score claim follows from preparation.
