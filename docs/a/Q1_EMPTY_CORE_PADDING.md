# P1: appending empty core schedules preserves the official simulation

Scope: the frozen official source identified by aggregate SHA-256
`de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`.
This is a source-level argument about that implementation, not a new benchmark.

## Claim

Let a legal plan have `k >= 1` core schedules. Keep its graph, mapping, Task IDs,
configuration, existing schedule lists and their order unchanged. Append
`K-k` empty lists, where `K >= k`. If the original evaluation completes, the
padded evaluation has the same Makespan, Task/op start and end times, DDR
contention events, COPY/spill bytes and memory peaks on the original cores.
It reports `K` cores and adds empty timelines and zero memory peaks for the new
cores. This does not claim that rebuilding a plan using K cores is monotonic.

## Source-level proof

1. `derive_multicore_plan` requires a nonempty *outer* schedule list and list
   entries; individual empty lists are legal. Appending them changes no
   scheduled Task, Task owner, membership, dependency pair or existing order.
   The augmented Task-order DAG gains no edge. The early-return condition in
   `validate_task_order` is also unchanged: it tests whether any core has more
   than one Task, and an empty list cannot change that predicate.
2. `_build_scene_a_tasks` visits the same sorted Task IDs and touched tensor
   IDs. Boundary ID allocation, local graphs and Step1/2/3 inputs are identical.
   Consequently their outputs, Task owners, predecessors and traffic counters
   are identical. None of this compilation uses total core count to change a
   Task's graph, capacity or bandwidth.
3. Couple the two event loops at time zero. Existing Task/op state and all
   existing executor/queue entries are identical. New cores have no Task, no
   ready operation, empty executors and empty queues. In each `retire`, the
   original executors are traversed in the same order; appended empty entries
   do nothing. Task completion checks therefore match. `activate_ready_tasks`
   skips each new core because its order is empty. `issue` visits all original
   cores/Pipes in the same order; the new queues issue nothing.
4. In particular, the DDR active-work dictionary, insertion/removal order and
   every arithmetic operation in `advance_ddr_work` and `reschedule_ddr` match.
   Bandwidth sharing depends on active requests, not declared core count.
   Thus this coupling preserves the frozen binary64/EPS computations, rather
   than appealing only to an ideal rational-bandwidth model. Added empty
   executor lists contribute no event time; added empty orders contribute no
   release time. The next clock value and iteration count are identical.
5. Induction gives identical original-core traces through termination. The
   maximum Task end is unchanged. The final output loops merely append empty
   core records and capacity peaks with `default=0`.

Relevant implementation: `data/raw/a/official/code/` files
`stub_multicore_cut_and_schedule.py::derive_multicore_plan`,
`evaluation_validation.py::validate_task_order`, and
`multicore_cut_evaluate_problem_1.py::_build_scene_a_tasks/evaluate_scene_a`.

## Consequence and research use

For the official plan space with a *budget* of K cores (empty schedules allowed),
the minimum attainable Makespan is nonincreasing in K: padding embeds every
feasible k-core plan in the K-core space with the same objective. This says
nothing about a particular heuristic's output as its requested K changes.

A solver may construct plans for selected active-core counts from the current
graph, pad and compare them online. It must charge all those constructions and
scores, freeze the selection rule, and avoid case-ID or saved-winner lookup.
The lower-core envelope of already recorded results is only a potential
estimate for such a solver, not its measured full-matrix performance or runtime.
The potential must justify any added online work; automatically running every
constructor at every smaller core count is not yet our chosen policy.

No new E0/E1/E2 call accompanies this argument. It assumes successful execution
with sufficient real resources and unchanged official settings; it does not
assert invariant wall time, output byte identity, core relabeling invariance,
or validity under a future rule requiring every core to be nonempty.
