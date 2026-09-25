# Exact-frontier quotient audit, recovered frozen run

The newly authorized recovery process ran once and completed for 005 and 086. The original `exact-frontier-audit/` process remains a separate failed hash-preflight record; total script processes across the two stages: two, of which only this one analyzed graphs. No candidate construction, Task, Step, pipe_bound, E0/E1/E2, or scoring call occurred.

| Case | Original ops | Rows | Exact nonrow components | Distinct `(U,D)` signatures | Row-only quotient vertices/edges | Joint quotient vertices/edges | Both acyclic |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 005 | 4,209 | 42 | 269 | 178 | 891 / 1,975 | 311 / 1,068 | yes |
| 086 | 5,372 | 48 | 296 | 200 | 1,004 / 2,348 | 344 / 1,280 | yes |

Every original op ID, including COPY, belongs to exactly one row or exact nonrow component. The grouped original `cycles` sums equal the raw graph sums on every pipe: 005 PIPE_M 63,882 and PIPE_V 60,930; 086 PIPE_M 79,182 and PIPE_V 78,060. Original COPY pipe cycles are zero. These are bookkeeping checks, not simulator runtime estimates.

The full `(U,D)` signature uses row **ID sets**, not just layers or key counts. Each nonrow signature class is split into weakly connected components in its induced original op graph. The first quotient contracts only each row; the second contracts each row and each exact component. Both quotient DAGs were topologically checked, and neither has a cycle in these two frozen graphs. The JSON retains all component op IDs, exact signatures, node-to-group mapping and empty cycle-witness fields. The script is prepared to save original graph edge chains for a quotient-cycle witness if one occurs.

The condition in the parent [FRONTIER_LEMMA.md](../FRONTIER_LEMMA.md) is therefore met for 005 and 086: row contraction itself is acyclic, so its path-convexity extension to full original paths applies to these exact nonrow components. This is a two-input structural audit, not a universal proof that every recognized row set can be contracted without a cycle. The parent's `a→x→b→y→c` toy example remains a counterexample when that condition is omitted. Joint quotient acyclicity is also an observed fact here, not a consequence inferred solely from the component names.

The exact components are suitable as checkable structure labels for a later constructor. They do not define a core owner, execution order, capacity/liveness schedule, zero-spill guarantee or score improvement. The recovery took 0.0592 s wall on this machine; this is static audit time, not solver time. Input hashes, the one-line script change, budget and reason for recovery are fixed in [FROZEN.md](FROZEN.md). Original stdout/stderr and full outputs are retained alongside this report.
