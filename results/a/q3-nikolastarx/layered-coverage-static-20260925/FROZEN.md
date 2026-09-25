# Frozen structural coverage audit

Commit: `e9ff04c3019dedadd5b2ff71ecfdd57ac1aabe4a`. Source: `src/q3/layered_query_flow.py` SHA-256 `db197556787c7818cad21c47dca52e497ba84ba56e1717d4616977fda0556d33`. Run only `RawIndex.build → _ports → recognize_layers(index,ports,_recognize) → decompose(index,labels,kv)`. Do not call `construct_layered`, `partition_tracks`, `priority_words`, any plan/solver routine, `pipe_bound`, Task/Step or E0/E1/E2.

Input matrix: all official `case_001.json` through `case_100.json`; ordered paths and SHA-256 values are frozen in `manifest.json`. Exact command: `python3 -B results/a/q3-nikolastarx/layered-coverage-static-20260925/runner.py --manifest results/a/q3-nikolastarx/layered-coverage-static-20260925/manifest.json`.

Budget: one process, one ordered pass, at most 100 calls to each specified structural stage, 60 seconds total, zero retries. Typed `GuardError`/`UnsupportedStructure` structural rejections from the frozen stages are recorded and the pass continues. The first unexpected exception or total timeout stops the pass. The track test records only the necessary condition `5 <= r <= 10` for K=5 and bounded subset-DP eligibility; it is not a full constructibility or feasibility result.

Interpretation is limited to structural coverage. It says nothing about capacity acceptance, official legality, official scoring, or performance.
