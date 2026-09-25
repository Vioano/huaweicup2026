# Private-chain return-cut resource relaxation

Fixed-source metadata run: `2587a0c1374a93bbbfe3540ffaf4e741b8dfb6d1`. Command: `python -B -m src.review.p1_return_cut_resource_bound --cases 008,084,095 --cores 5 --output results/a/p1-return-cut-bound-20260925/report.json`. Locked Python 3.12.13; graph/config/archive SHA checked before analysis. Three raw-graph metadata calculations; **0 Task compilation, response simulation, solver, E0, E1, E2**. Runtime 0.179182 s excludes interpreter startup.

| Case / K5 | Integer resource bound | Existing v4 E0 Makespan |
|---|---:|---:|
| 008 | 76020 | 100603 |
| 084 | 335819 | 399121 |
| 095 | 322992 | 420852 |

The middle column is the optimum of an optimistic resource relaxation under the private-chain/same-core/whole-or-final-return-cut premises. It is **not a new score**, not a verified E0 lower-bound certificate, and not an achievable schedule. The right column is read from fixed v4 feed `0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297`, not re-evaluated here. The distinct model/numeric scopes mean their differences are research guidance, not certified official optimality gaps. These bounds do not rule out further improvement.

See `docs/a/P1_RETURN_CUT_RESOURCE_BOUND.md` for the proof, numeric limits, and source-level review. Four pure tests passed: integer resource optima checked against independent exhaustive cut assignments over 48 small parameter combinations (396 cut assignments); one fractional intersection; two cache-probe guards. Those checks do not exercise a real cache compiler.
