# Shared-input pipeline mechanism probe

Source `87f677f8f16e31a71c071d49dd176d4420efb36d`, entry `src.q3.pipeline_solve`.
The original three-case manifest was superseded **before any dispatch**, after a certified static check excluded 067/k5. Its candidate lower bound is 13,321,680 cycles, already above the frozen calendar incumbent 12,237,901. This rejects this particular submitted plan only, not all pipelines or its whole graph family. No E0 was used for this decision.

Use only `manifest-v2.json`: 044 and 046 at5cores;2solver/at most6onlineE0;120s total/30s per job,1worker,0retry. This is a seen-case mechanism probe, not a full500 score. 044/046 represent11 and8 repeated jobs of124 positions with shared inputs. Their candidate bounds25412/70776 do not exclude improvement on incumbent83958/88200; lack of pruning is not a prediction of actual improvement.

`static-census.json` records all100 input structure coverage(8 accepted), while `static-lower-check.json` retains the exact three pre-dispatch checks. DP uses only graph structure and durations; case IDs are evaluation coordinates, not runtime tuning. All baseline/calendar computations in the future solver invocation must be fresh and counted.

Validation:138 tests run,137 passed,1 explicitly gated E0 test skipped. Static constructors and lower-bound checks made0E0/E1/E2 calls. Source adapted from Fang6bae, no new upstream cut research or writes in his directory.

## Frozen candidate-family ceiling (zero E0)

`candidate-family-bound.json` checks this same deterministic pipeline plan on every recognized graph and2–5cores, comparing its certified relaxed lower bound with the complete calendar incumbent. For each coordinate, selecting between the incumbent M and this one plan can improve speedup by at most `max(0, baseline/LB - baseline/M)`. Summing over the100 graphs yields a mean upper bound; it does not assert that independently optimistic bounds are jointly attainable.

| Cores | Proposals pruned /8 | Current mean | Mean upper bound for this exact extension | Screenshot target |
|---:|---:|---:|---:|---:|
|2|7|2.308188|2.313884|2.28|
|3|6|3.239165|3.260394|3.23|
|4|7|4.053230|4.085163|4.09|
|5|5|4.673441|4.726138|4.76|

Thus this fixed extension alone cannot attain the numeric4/5-core targets, even if every unpruned plan attained its relaxation bound. It remains a useful bounded component, not the entire remaining research direction. This does not bound other cut positions, other pipeline schedules, Attention splitting, or the official global optimum. No graph was rescored and no performance result is inferred from the bound.
