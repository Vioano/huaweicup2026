# P1 saved lower-core envelope

This is a retrospective arithmetic calculation, not a new algorithm result.
The fixed v4 full500 feed and all 100 referenced baseline hashes are recorded
in summary.json. No new solver, E0, E1 or E2 calls were made.

At K=5, the mean of the 100 per-graph single-core-baseline / Makespan ratios
is 4.025907473836023 for the frozen algorithm and 4.0368583447 for the
lower-core envelope. Fourteen K=5 cells and two K=4 cells could improve
by choosing one of the already recorded lower-core plans. This is potential
under the source-level empty-core-padding result in
[Q1_EMPTY_CORE_PADDING.md](../../../docs/a/Q1_EMPTY_CORE_PADDING.md).
It does not establish a new unified full500 result or solver runtime.

The largest K=5 contribution to mean speedup is graph086, using four cores;
the largest absolute cycle drop is graph080. Aggregate cycle reduction is
an auxiliary statistic and must not replace the mean of individual ratios.

`audit.py` is the executed arithmetic script with only repository/output path
resolution made portable. It reads the fixed source via git and writes a
separate recomputed-summary.json; the original summary is preserved.
Do not build a runtime lookup table from this retrospective comparison.
