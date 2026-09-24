# Shared-input pipeline mechanism probe

Source `87f677f8f16e31a71c071d49dd176d4420efb36d`, entry `src.q3.pipeline_solve`.
The original three-case manifest was superseded **before any dispatch**, after a certified static check excluded 067/k5. Its candidate lower bound is 13,321,680 cycles, already above the frozen calendar incumbent 12,237,901. This rejects this particular submitted plan only, not all pipelines or its whole graph family. No E0 was used for this decision.

Use only `manifest-v2.json`: 044 and 046 at5cores;2solver/at most6onlineE0;120s total/30s per job,1worker,0retry. This is a seen-case mechanism probe, not a full500 score. 044/046 represent11 and8 repeated jobs of124 positions with shared inputs. Their candidate bounds25412/70776 do not exclude improvement on incumbent83958/88200; lack of pruning is not a prediction of actual improvement.

`static-census.json` records all100 input structure coverage(8 accepted), while `static-lower-check.json` retains the exact three pre-dispatch checks. DP uses only graph structure and durations; case IDs are evaluation coordinates, not runtime tuning. All baseline/calendar computations in the future solver invocation must be fresh and counted.

Validation:138 tests run,137 passed,1 explicitly gated E0 test skipped. Static constructors and lower-bound checks made0E0/E1/E2 calls. Source adapted from Fang6bae, no new upstream cut research or writes in his directory.
