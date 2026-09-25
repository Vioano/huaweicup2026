# Startup-aware proxy: static evidence only

The constructor and proof are in `src/q3/pipeline_startup.py` and
`docs/a/q3/PIPELINE_STARTUP.md`. `summary.json` identifies exact source bytes,
test command/scope and actual delegated execution count. Four static test
methods passed; two full invocations occurred because a floating metadata
field was removed before the final recheck. No E0, solver, Task or Step3 ran.

Both previously observed graphs produce different cuts. Against the capacity
minimax cuts, the new proxy falls by 68.9333 cycles for 044 and 909.6 cycles
for 046. These are surrogate differences, **not performance improvements**.
The 044 surrogate gain is small; large future gains likely need a better
pipeline startup model or a broader legal construction, not repeated nearby
cut trials. This is a research prioritization inference, not a global bound.
The existing frozen `capacity_solve` and its pending smoke remain unchanged;
this new constructor has not been incorporated into an online solver.
