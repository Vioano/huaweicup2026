# R8 071/K5: official pair improves both execution modes

## Task and fixed scope

The task was to falsify or validate one query-flow affinity plan on original case
071 with five cores, using unchanged official P3 followed conditionally by P2.
Source: `65d7355ee0856783ede81328915e8bd43227c842`.
The saved plan was originally constructed at
`b1eb32aca82436b20cc82da8c86d4301ef00cfb1`; `git diff` confirms the complete
`src/q3/` source trees at these two commits are identical. The later commit
freezes the official probe, without attributing a second construction to it.
Plan SHA-256: `b0ccb1c9d9e2f90ae6566ecaa725a0440c47d942401a3cdcb261d90eb0968136`.
The plan and its prior static certificate remain in
`../query-flow-static-repair-20260925/run/`. No input, configuration, or official
evaluator was modified. This is a local mechanism experiment, not a full solver
benchmark or a replacement for the fixed 500-cell result.

## Result

The old comparison is the same fixed forest solver's 071/K5 plan, with its
matching no-cache result from evidence commit
`19bebf35205d23fdd832781540f8879da52eeb62`. `compare.py` rehashes the old and new
official result bytes and checks graph/configuration/plan-pair identities.

| Metric | Old plan | R8 plan |
| --- | ---: | ---: |
| P3 cycles, with cache | 7782 | 5785 |
| P2 cycles, without cache | 8581 | 7070 |
| Same-plan G = P2/P3 | 1.102673 | 1.222126 |
| Official single-core baseline / P3 | 2.431123 | 3.270354 |
| Additional DDR copy bytes | 333138 | 272184 |
| Spill bytes | 0 | 0 |
| Byte cache hit rate | 0.401696 | 0.297990 |

P3 improves by 25.6618%; P2 improves by 17.6087%. The increase in G is therefore
not obtained by making the no-cache execution worse. The lower byte hit rate
does not negate the cycle improvement: the submitted plan and its copy stream
have changed. These observations do not prove the relative contribution of
each scheduling/cache mechanism; that requires a controlled timeline analysis.

## Validation and calls

Both official workers exited with code zero, and `run/run.json` is complete.
The P3 worker passed the frozen physical tensor/capacity, FIFO, dependency,
spill, and copy-byte guards. Each of P3 and P2 was entered exactly once, with
one Task and five calls each to Step1, Step2, prepareStep3 and simulation per
phase. There were no E1/E2 calls, retries or extra standalone preparation.
The original two-E0 allowance is fully spent. Case 069 was not evaluated.

The parent probe's diagnostic wall time is 2.848999 seconds, including both
official phases and evidence work. It begins with an already constructed plan;
`solver_wall_seconds` remains null. It is not a cold end-to-end solver timing.

## Resource-supervisor failure boundary

The external supervisor used SHA-256
`651a8a9ee62253961abc656bfa50e01cdca4e17b5f799ad7d233826dcd438fa7`.
Its receipt remains **failed**, with `parent identity or process group
unverified` and the same cleanup error, after the two workers and probe had
completed. This is not rewritten as a successful supervised run. Four resource
samples saw pressure level 1, no other scorer, and physical free memory at least
9.525 GiB; sparse samples do not establish the true peak RSS.

Independent subsequent PID readbacks found no surviving recorded processes,
and the coordinator independently checked and released the exclusive window.
The exit-identity ordering issue is analyzed in
`resource-control/TERMINAL_IDENTITY_AUDIT.md`; the exact failed identity branch
was not captured. No cleanup signal or retry was issued. Numerical phase
results, supervisor failure, and later process absence are separate facts.

## Deliverables and next action

- `run/`: unchanged official P3/P2 gzip results, worker claims/reservations,
  prepared trace, call ledgers and probe receipt.
- `resource-control/`: original failed supervisor receipt, observations,
  stdout/stderr, independent postcheck and bounded diagnosis.
- `comparison.json` and `compare.py`: source-linked old/new pair comparison,
  with zero new scoring. The first comparison attempted a nonexistent official
  P2 `problem` field; the corrected reader uses its actual scene/schema and
  frozen worker identity. This reader correction did not change or rerun any
  evaluation.
- `export/`: separately prepared board feed and validation, retaining the
  failure/timing limitations; receiver acceptance must be recorded separately.

Next, incorporate graph-based recognition into a fixed solver and verify its
selection rule and full running cost. The current complete 500-cell benchmark
remains unchanged. Even replacing only 071 and 069 with their exact R8 plans
cannot establish a five-core mean above five; the conditional ceiling from
their archived plan bounds is 4.7905054 (`../query-flow-target-gap-20260925/`).
