# R9 static construction reproduction freeze

This is a pure constructor reproduction only. It does not call official Task/Step, E0/E1/E2, `pipe_bound`, or a scorer. Frozen source is commit `2f74818b81155c9439392622296716d4bc6c4005`, `src/q3/layered_query_flow.py`, SHA-256 `db197556787c7818cad21c47dca52e497ba84ba56e1717d4616977fda0556d33`. Public callable: `construct_layered(graph, cores=5, *, capacity, cross_delay_cycles)`.

Inputs: official `case_005.json` and `case_086.json`, plus official `config.txt`. Their SHA-256 values are recorded in `manifest.json`. The unmodified official parsers provide `capacity={'L1':524288,'UB':131072}` and `cross_delay_cycles=500` (`read_evaluation_config` and `read_scene_b_config`); no parameter was guessed. Pro candidate raw-plan SHA-256 values are fixed to `2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a` (005) and `f2111af54fcc3c11048663db149a93290dbe4558e7d5b7eecf8ec49e847022e6` (086).

Budget: one worker, at most one independent child constructor process per case, 60 seconds per case, 180 seconds total, zero retries. First exception, timeout, or comparison failure stops before starting the next case. The runner captures UTC start/end, wall time, claim, stdout/stderr, and failure; originals are retained. No source changes are permitted.

Comparison: retain generated plan bytes; compare parsed structure for exact object equality and compare canonical JSON encodings (sorted keys, compact separators, UTF-8, no NaN) separately. Also report raw byte equality and both raw/canonical hashes. A mismatch stops immediately; no algorithm repair or rerun.

Acceptance boundary: successful construction plus plan comparison only. This is not official simulation, official Makespan, solver end-to-end time, or a general acceptance result.

Exact invocation: `python3 -B results/a/q3-nikolastarx/layered-port-static-20260925/runner.py --manifest results/a/q3-nikolastarx/layered-port-static-20260925/manifest.json`
