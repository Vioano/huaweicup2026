# Same-plan P3 paper figure assets

These plots use the audited `final-export-20260926/comparison.csv` from evidence snapshot `2c24a0eec7671abf9745f48b5eea0146b98a5aae`. No solver/evaluator or new candidate was run. Every K has 100 pairs with identical plan, graph, config and official identity.

## Main comparison for paper task 6-3

`same-plan-main-figure/p3-same-plan-speedup-by-core.{png,pdf,svg}` uses core count K=1..5 on x. The two curves are arithmetic means of per-graph **B_i/M2_i** and **B_i/M3_i**, with the same official single-core B_i for both modes. They are not meanG and not ratios of summed cycles. The P2 plans are the exact selected P3 plans evaluated without L2, not the independent P2 solver's winners.

Reproduction (new output directory required):

```sh
python -B -m src.q3.final_same_plan_speedup_figure results/a/q3-nikolastarx/r9f-final-full500-20260926/final-export-20260926/comparison.csv NEW_OUTPUT_DIRECTORY
```

`plot-data.json` gives the five numeric points. `metadata.json` records input/script/output hashes. K5 means are P2=4.476283315658887 and P3=4.7576166788448955; their quotient is not the mean same-plan Cache gain 1.082917172693062.

## Per-case appendix

`same-plan-figures/p3-same-plan-cache-comparison.{png,pdf,svg}` displays five raw-cycle paired curves, one panel per core count, each with cases001..100. All five panels share log-scaled cycle limits. The sixth panel reports mean_i(M2_i/M3_i). It is a pair audit/detail asset and does not replace the core-count main comparison above. Reproduce with `src.q3.final_cache_pair_figure` and the same CSV.

Both PNGs were opened and visually inspected: complete axis labels/legends, all core counts/cases present, matching curves honestly overlap, no cut-off or title collisions. PDF/SVG share the rendered figure source. These are P3-owned research assets for the paper editor; they do not claim ownership or acceptance of LYX's final paper figure tasks.
