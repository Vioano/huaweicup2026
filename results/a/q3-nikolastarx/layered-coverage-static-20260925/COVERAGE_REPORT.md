# Layered structural coverage audit

The frozen single-process pass read all 100 official graph inputs in order in 7.952014 seconds (2026-09-25T14:06:26.243137Z–2026-09-25T14:06:34.195151Z). It used source commit `e9ff04c3019dedadd5b2ff71ecfdd57ac1aabe4a`, source SHA-256 `db197556787c7818cad21c47dca52e497ba84ba56e1717d4616977fda0556d33`.

It recognized and decomposed 22/100 graphs; 78 returned typed structural unsupported results. The success set includes the prior demonstration graphs 005 and 086, plus 009, 031, 035, 040, 043, 047, 048, 049, 053, 064, 068, 069, 071, 072, 075, 077, 082, 085, 087 and 088. Thus the recognizer is not limited to 005/086, while its measured recognition/decomposition coverage on this fixed 100-graph set is 22%.

Among the 78 typed rejections, 73 stopped in `recognize_layers` because no closed attention query row matched; 3 stopped in `decompose` with a genuine cross-stream bridge/join (two keys of one depth in one lineage); 2 stopped in `decompose` because the shared auxiliary set was not ancestor-closed. There were no unexpected exceptions or timeouts.

Of the 22 decomposed cases, 13 had 5–10 tracks, satisfying only the necessary K=5 bound for the later bounded subset-DP stage. Nine were outside it: five had 4 tracks, one had 3, and one each had 11, 13, and 15 tracks. The full distribution is in `coverage_summary.json`. This is not a complete constructibility judgment.

`coverage.jsonl` retains all per-case counts, stage, reason, wall time, and frozen input SHA. `run_summary.json` records claim, overall interval and a zero call ledger; runner stdout/stderr are preserved. `RESOURCE_PREFLIGHT.md` summarizes the pre-run memory/load and process inspection. The only invoked stages were `RawIndex.build`, `_ports`, `recognize_layers`, and `decompose`. Total actual graph passes: 100 once each. Task=0, Step=0, E0=0, E1=0, E2=0, `pipe_bound`=0; no plans were generated. No capacity/official legality, official score, full solver timing, or performance claim follows.
