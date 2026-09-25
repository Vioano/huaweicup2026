# Saved-trace DAG audit

`src/review/p1_saved_trace_causal_audit.py` reads the frozen `whole_seed` or `period7_seed` Task signatures
(SHA-256 `2a90a5b0e8b3ff19fe88a07e6580dc4899a63b7654d0d268c0941b947549c95b`) and a
later **already recorded** response result containing `trace`,
`task_intervals`, and integer `makespan`. It never calls the response model,
compiler, solver, or an evaluator. Run it only after the R5 trace file exists:

```sh
python3 src/review/p1_saved_trace_causal_audit.py \
  --variant period7_seed --trace-json PATH_TO_SAVED_TRACE.json \
  --output /tmp/p1-period7-audit.json
```

The output path must not already exist. Each `(Task, Pipe)`
trace subsequence is paired with saved signature ranks in retirement order.
The checker rejects missing operations, out-of-order retirement, Pipe overlap,
work/DDR mismatches, unmet FIFO or completed-prefix needs, bad Task intervals,
gate mismatches, and inconsistent makespan. The CLI also requires the trace
makespan to equal that variant's saved model makespan. Equal-time events on **different**
Pipes are allowed; same-Pipe ordering must be unambiguous. It then builds one
global weighted DAG with Task start/end and gate nodes. An exact match of that
DAG length to the recorded makespan is only a consistency check on the observed
durations; otherwise the result is `undetermined_hidden_delay`.

Path decomposition separates compute work, DDR solo work, observed DDR duration
above solo work, and gate. The DDR excess includes both shared-service effects
and integer retirement/rounding; it is **not** a counterfactual estimate of
pure congestion or an attribution of every wait. **This is not a fair-DDR
service validator**: it checks precedence algebra, not whether observed DDR
durations could arise from the model's service rule. The signatures omit original
operation IDs, so the checker verifies rank, work, and need, not op-ID identity.
It does not establish E0 equivalence or validate how a trace was produced.

`synthetic-validation.json` comes only from a hand-written two-Task, one-core
trace. Its sole DDR operation has solo work 2 but deliberately assigned duration
3 without a contender: this violates fair service, yet the precedence DAG still
matches length 11 = DDR solo 2 + excess 1 + compute 6 + gate 2. That is an
explicit limitation demonstration, **not a physically valid trace**. Missing,
out-of-order, duplicate-schedule and premature-need inputs are rejected. A second
hand-written feasible schedule checks the no-contention decomposition
10 = DDR solo 2 + compute 6 + gate 2. Neither is a case result.

The root replayed the hand-written validation with the project Python 3.12.13:

```sh
python -B src/review/p1_saved_trace_causal_audit.py --synthetic-self-test --output /tmp/p1-trace-synthetic.json
```

This preparation does not add a real-case score or alter any production solver.
R5 fixed-plan trace artifacts are still pending; do not fill missing rows from
prose, hidden reasoning, or guessed operation IDs. The original whole/q7 files
and graph remain unchanged.
