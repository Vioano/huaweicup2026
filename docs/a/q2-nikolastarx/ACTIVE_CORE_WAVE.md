# Shared-input waves with a core budget

After the ee1 full500 regression audit, this entrypoint preserves whole-component
ownership when enough independent components exist. It no longer infers that
internal splitting helps from `largest_component_work > balanced_work` alone.
The old `adaptive_frontier` entrypoint keeps its frozen policy for reproducibility.
This revision is later than the b4 active-core prototype and requires its own
full-suite run; neither b7 nor ee1 results are its achieved scores.

All twenty four-core and twenty-two five-core regressions in the paired audit
belong to the added `dominant_component_dag` route. It also improves eight and
nine cases respectively, so this is not a theorem that splitting is useless.
Each shared-input-wave route improves all nine cases at each of those core
counts. New split proposals need a cost decision that accounts for COPY and
memory, rather than the failed balance-only proxy. E2's current P2 interface
can compare complete plans, but new-plan cold preparation is substantial and
its existing 32-plan validation does not cover this new candidate family.

`adaptive_budget` is a new algorithm version. The currently assigned full500
experiment remains fixed at `ee1b8fd` / `adaptive_frontier`; it does not use this
new version. No original-graph solver or official evaluation has yet been run
for `adaptive_budget`.

## Why fewer cores can help

For `n` repeated independent jobs, let `W` be a job's largest Pipe workload,
`H` its compute critical path, `S` the bytes of inputs shared by every job,
`P` the remaining distinct external-input bytes, and `B` the DDR bandwidth.
For `q` balanced active cores, use the relaxation

`L(q) = max(ceil(n/q) W, ceil((q S + P)/B), H)`.

This ignores output traffic, COPY eligibility/delay, queue order, overlap
constraints and spill. Its optimizer is a construction heuristic, not an
official optimality proof or performance guarantee. It applies only after the
existing repeated-component guard and positive integer M/V-work checks.

The compute term is nonincreasing and the input term nondecreasing. Find their
first crossing by binary search, and compare that point with its predecessor.
Before the crossing the maximum equals compute; after it equals input. The
constant critical-path term preserves the minimum but can extend a plateau.
Given minimum value `F`, the earliest compute-feasible core count is
`ceil(n / floor(F/W))` for positive `W`, clamped to the allowed minimum. Input
traffic cannot increase on moving left from a minimizer. Thus this selects the
smallest minimizer in `O(log k)` arithmetic, without constructing and evaluating
a grid of plans. Work zero is handled separately.

Read-only workload extraction from the frozen input graphs predicts two active
cores for 044 under a five-core budget, four for 083 under four, and five for
092 under five. These are predictions from the relaxation, not new results.
For 044, the compute/input pairs for q=1..5 are
74404/15883, 40584/31389, 27056/46896, 20292/62403, 20292/77909 cycles.

## Capacity guard and scope

Fewer cores mean more jobs per core. For each actual job, project the existing
wave sequence onto that job and compute its private-tensor raw touch peak.
Take the largest per-pool value `Pmax`. At most one shared wave input is live
under the recognizer, so `m Pmax + Smax` bounds raw priority touch for a group
of at most `m` jobs. Private aliasing and ID-dependent traversal are handled by
scanning every job, not assuming job 0 has every private lifetime pattern.
See [the capacity derivation and corrected boundary counterexample](WAVE_CAPACITY_DERIVATION.md).

This bound restricts the minimum active-core count. If even the requested
count cannot satisfy it, retain the existing requested-core wave plan and
report the uncertainty. Passing the bound is not an official zero-spill
certificate. The new guard falling outside its domain also preserves the old
wave route. Exactly one final plan is constructed and empty schedules pad it
to the requested core budget. No case ID, stored score or online evaluator
controls the choice. Recognition and private-lifetime scans are linear in
the represented graph apart from the existing recognizer's matching work;
the legacy wave builder currently repeats recognition once, included in
future measured solver wall time.

Validation uses exhaustive small-domain comparison of the binary-search
optimizer against direct arithmetic enumeration, plus synthetic padding,
capacity rejection, fallback preservation and existing adaptive-route tests.
Official quality, whole-suite regression and end-to-end time remain pending.
