# Guarded P1 structural refinement

`python -m src.q1.structural_refine INPUT --cores K --output PLAN --diagnostics DIAG`
is a separate research entry point. The production v4 entry is unchanged.

1. Run the existing variable-packet response wrapper. It first solves with v4
   and conditionally tests one variable-packet candidate for a scored
   capacity-return winner.
2. Recover a successful online E1 score matching the exact current output's
   serialized SHA-256. For a variable-packet winner use its refinement score;
   otherwise require the matching named v4 candidate score. Without that
   evidence, retain the parent output and do no further construction/scoring.
3. For at least two cores, apply the strict intact fork/join recognizer. Only
   its accepted all-PIPE_V domain receives the paced and root-heavy-fused
   constructions. Validate their Task/core order and byte-deduplicate them.
4. Score at most two extra plans with one E1 worker. Replace the incumbent only
   on strict improvement in `(Makespan, scheduled_COPY_bytes)`. A construction,
   validation or scoring failure stops this refinement and retains the last
   checked winner. An unexpected recognizer exception also retains the parent.

The route uses graph structure and the current solve's scores, with no case-ID
table or historical plans. The rejected full-core shared-input candidate is
not part of this entry. The graph-domain arguments explain why each of the
two extra candidates exists; this is not an unrestricted parameter sweep.

The conservative total is at most six v4 E1 calls, one packet-refinement E1
call and two intact-refinement E1 calls. The latter two use one worker, a
60-second per-item timeout and a two-item worker lifetime. Packet construction
retains its separate 120-second child limit and compilation caps. Diagnostics
include parent and extra wall times and call counts; unknown dispatch counts
remain unknown. External process wall time is required for full solve timing.

Seven injected controller tests cover strict improvement, ties/regression,
score failure after an improvement, exact-byte deduplication, missing parent
score, variable-packet parent score matching, and unexpected guard failure.
They do not execute real solvers, Task compilation, E1 or E0.

## Evidence boundary

The constituent constructors have separate local and historical evidence, but
their combination needs a frozen-entry pilot and then a complete 100-by-5
matrix. E1 ranking is not external E0 acceptance. A source hash or a passing
controller test does not establish full-matrix quality, runtime or global
optimality. The accepted full-matrix result remains v4 until that validation
is completed.
