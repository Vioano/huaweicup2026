# Guarded component comparison (mechanism only)

`guarded_component.make_component_builder(oracle)` supplies the callback accepted by
`adaptive_semantic.build(graph, cores, config, component_builder=...)`. The caller
provides an oracle that scores a **complete plan** and returns a mapping with
`status: "ok"` and exact nonnegative Python integer fields `makespan` and
`added_copy_bytes`. Other statuses fail even when numeric fields are present. Scores are
compared lexicographically; an exact tie keeps `adaptive_budget.component_route`.
The module does not import or call E0/E1/E2 and has no CLI.

The baseline is constructed first. Only when `cores > 1` and
`component_pressure.component_exceeds_balanced_pipe_work` is true is a DAG plan
constructed. Recognized vector templates return the baseline without scoring,
leaving the existing `adaptive_semantic` repair path in control. This pressure is
a reason to compare, not evidence that splitting helps. Equal plans need no
score. Otherwise the baseline gets one oracle request.
If its score is valid, candidate pipe work is summed from the candidate's actual
operation-to-core assignment for each pipe. This excludes COPY and is a lower
bound only; the candidate can be skipped safely when that bound is **strictly**
greater than baseline makespan. Equality still needs scoring because DDR bytes
could improve. A remaining candidate gets one oracle request. At most two plans
are constructed and at most two oracle requests are made.

Missing, Boolean, floating, negative, or failed scores are unknown evidence.
Candidate construction and oracle failure preserve the baseline and are recorded
in `detail.guarded_component`; they do not establish a quality guarantee. The
caller must count construction and scoring in end-to-end solver wall time and
include oracle calls in the evaluation ledger. The score comparison applies to
the plan returned by this callback. Recognized vector templates bypass it;
a caller requiring a scored repaired plan must evaluate the post-repair output.

Validation here uses small synthetic graphs and injected oracle values only.
No original case, official evaluator, solver speed, or final score claim follows.
