# P3 five-core coverage ceiling for the current fixed solver

This is a read-only mathematical screen. It adds no official evaluation, no new
solver run, and no new plan. `reproduce.py` joins the frozen 100-case R9
recognition snapshot, the validated graph-independent compute lower bounds,
and the **same fixed Forest500 solver's** 500-cell record snapshot. It checks
case and graph hashes, all 500-cell coverage, the solver commit, and the K5
baseline/speedup identity. Exact source-file hashes and all 22 joined rows
are in `ceiling.json`.

Let `B_i` be the fixed official single-core baseline, `T_i` the current
Forest500 P3 makespan, and `L_i` the valid but optimistic compute-only lower
bound for five cores. If only a set `S` of cases improves, while all other
cases stay at their current value, its **largest possible** contribution to
the 100-case arithmetic mean is

```
sum(i in S, (B_i / L_i - B_i / T_i) / 100).
```

Current K5 mean is **4.7576166788448955**, requiring **0.24238332115510453**
additional mean speedup to reach 5. The five recognized four-track cases are
031, 035, 064, 068, and 088. Their combined optimistic contribution is only
**0.13145594279936743**. Even if all five somehow reached their lower bound
and all other cases stayed fixed, the mean would be at most
**4.889072621644263**. Thus optimizing this four-track family alone cannot
meet the user's K5 target under the stated fixed-others condition. This is an
upper-bound argument, independent of whether Pro's 068 fifth-core plan is
good. It does **not** say fifth-core work is useless: it can be a reusable
mechanism and improve individual cases.

All 22 recognized R9 cases together have an optimistic mean-increment ceiling
of **0.47469900137999954**. Reaching mean 5 using only those cases would
require at least **51.06%** of that *loose* theoretical slack, without any
regressions. This is a necessary arithmetic threshold, not evidence that the
gain is attainable. The general fallback and other unrecognized structures
also remain legitimate optimization targets.

The frozen lower bounds omit COPY, cache, capacity and scheduling effects;
they can be far below achievable official makespan. We do not infer a new
full500 score, plan legality, solver time, or paired Cache gain from this
screen. Historical per-cell winners do not enter the arithmetic. Prior R8/R9
single-case updates are intentionally not spliced into the Forest500 record.

Reproduce with `python3 results/a/q3-nikolastarx/layered-coverage-ceiling-20260926/reproduce.py > /tmp/ceiling.json` and compare the generated JSON with `ceiling.json`. No evaluator is imported or called.
