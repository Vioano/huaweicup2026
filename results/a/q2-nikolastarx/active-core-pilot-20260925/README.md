# P2 active-core pilot preparation (044/k4)

This existing one-cell batch is prepared for the frozen solver source commit
`2794ceba93acc1f7fc119154f61082511843d4b3`. The local macOS
`evaluate_feedback.py` and `evaluate_matrix.py` runner remain on this branch;
their separate runner commit must be supplied at execution. The source changes
copied from the frozen commit are `adaptive_budget.py` and
`adaptive_frontier.py`. The pilot now defers a component split based only on
compute imbalance, while retaining the guarded active-core choice.

Any preflight for the earlier `b4ea8aa75310952d6ca7fb809efa8c3df99c2ebf`
source is superseded. There is no prior dispatch or run output in this batch.
After the preparation changes are committed, the production owner should run
`python3 results/a/q2-nikolastarx/active-core-pilot-20260925/run_pilot.py
--runner-commit <full commit SHA>` without `--run` and record the resulting
preflight as evidence for that exact commit. This documentation is preparation,
not a dispatch authorization or an official result.

The frozen allocation is one 044/k4 solver call and one final E0 call, zero
online E0, E1, E2, or retries; one worker; 25 s solver, 50 s E0, 85 s cell,
90 s aggregate, and a sampled 4 GiB RSS stop. The production session
`nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc` controls dispatch after
resource release.
