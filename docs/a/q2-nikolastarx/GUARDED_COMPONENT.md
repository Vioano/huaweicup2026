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
could improve. After that pipe screen, the route counts the candidate's
mandatory original P2 Scene B COPY operations with `candidate_ddr.mandatory_copy_work`.
It records the complete counter in `detail.guarded_component.candidate_mandatory_ddr`
and its model in `candidate_mandatory_ddr_model`. The count includes boundary
input/output and cross-core tensor/direct-edge COPYs, with shared DDR service
work `sum(max(1, ceil(size / bandwidth)))`. Step2 spill COPYs are omitted, so
they can only strengthen the bound. If this work is **strictly** greater than
the baseline makespan, the candidate needs no complete score. At equality the
candidate is still scored for the DDR-byte tie-break. Unsupported config or
counter failures are recorded as `status: unknown` and leave the complete
oracle comparison in place. A remaining candidate gets one oracle request.
At most two plans are constructed and at most two oracle requests are made.

Missing, Boolean, floating, negative, or failed scores are unknown evidence.
Candidate construction and oracle failure preserve the baseline and are recorded
in `detail.guarded_component`; they do not establish a quality guarantee. The
caller must count construction and scoring in end-to-end solver wall time and
include oracle calls in the evaluation ledger. The score comparison applies to
the plan returned by this callback. Recognized vector templates bypass it;
a caller requiring a scored repaired plan must evaluate the post-repair output.
The COPY counter accepts finite positive bandwidth and size/duration values
within its documented binary64 exact-integer domain. Its service-work bound is
an abstract model statement, not a claim of bit-level equivalence for every
official floating-point execution. This adds one inexpensive rejection screen;
it does not implement the Pro answer's full lower/upper bound decision branch.

Validation here uses small synthetic graphs and injected oracle values only.
No original case, official evaluator, solver speed, or final score claim follows.
