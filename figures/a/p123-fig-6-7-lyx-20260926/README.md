# Figure 6-7 delivery

This package uses the fixed forest revision-2 feed (500 unique case/core cells) and keeps quality and wall-clock values from the same record.

- Source commit: `19bebf35205d23fdd832781540f8879da52eeb62`
- Solver commit: `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`
- Reproduce: `python figures/a/p123-fig-5-6-lyx-20260926/plot_figures.py --figure 6-7`
- Outputs: `fig67_p3_quality_cost.png`, `.svg`, `.pdf`, `p3_quality_cost_rows.csv`, `solver_wall_quantiles.csv`
- Budget: read-only parsing and plotting; no new solver or evaluator calls.
