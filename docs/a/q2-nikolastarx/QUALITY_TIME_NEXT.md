# P2 measured time and next quality/time experiment

The verified full500 solver source is
`2794ceba93acc1f7fc119154f61082511843d4b3`. Its five-core arithmetic mean
speedup against the common official single-core baseline is 4.014094174565.
This is one fixed algorithm, not a per-case historical combination.

Recorded external solver wall time over all 500 cells: mean 0.434088 s,
median 0.318349 s, nearest-rank P95 1.142867 s, maximum 2.043314 s.
Separately, final external E0 evaluation: mean 1.857702 s, median 0.710952 s,
P95 8.196310 s, maximum 26.322925 s. The batch ran four concurrent workers on
the captain's Mac; these are not exclusive-machine or cross-platform promises.
Solver/evaluator children used Python 3.12.13; the batch controller used 3.14.5.

Source: `results/a/q2-nikolastarx/active500-audit-20260925/paired.csv`.
Reproduce these summaries with the adjacent `timing.py`; `timing.json` records
the input hash. No new solver or evaluator is called by this analysis.

Solver timing includes process startup, input reading, online construction and
plan output. This fixed solver has no online E0/E1/E2 selection. Future online
evaluation, initialization and fallback must be included in solver timing;
native replay kernel time alone is not end-to-end cost.

The official 5–10 minute recommendation directly annotates P1; P2 asks for a
stable, efficient method. The team adopts the recommendation as guidance, not
an independently specified P2 hard deadline, minimum runtime, or per-core
allowance. The original also discourages brute iterative search. See
`docs/a/OFFICIAL_OBJECTIVES.md` for the exact source and scope.

## Proposed experiment, not dispatched

Preserve the subsecond constructive baseline. Compare a fixed general policy
with structured refinement budgets at roughly 5–10 seconds and 30–60 seconds,
including all scoring costs. First freeze the policy, candidate rationale,
stopping rules and resource budget; schedule a small pilot before any full500
batch. No new experiment is authorized by this document alone.

Extra time should buy new effective constructions: split a bottleneck component
without scattering every operation, preserve tensor locality across chains or
larger regions, and score only promising complete plans. Static pipe/mandatory
DDR screens can reject hopeless candidates, while full evaluation resolves
contention, spill and memory-dependency effects. Repeatedly trying the same weak
candidate family is not a credible route to a qualitative improvement.

Compare quality/time frontiers with the same algorithm across all 100 cases and
1–5 cores, recording regressions, tails and failures. Stop increasing a budget
when additional quality does not justify cost. Structural-family holdouts and
perturbations should test generalization; accepting jagged scores alone does
not prevent overfitting. No magnitude of future gain is established yet.
