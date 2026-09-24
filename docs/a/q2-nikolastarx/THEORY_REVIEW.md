# Targeted Pro audit and current mathematical boundaries

The current implementation follows Pro2 R2 §4.2–4.5 and Pro4 synthesis §4 / f0ff
reply; it does not endorse every archived conversation or import the proposed
D3 experimental budget. The six-case protocol is independently frozen.

1. **Priority compilation.** Within an assigned independent component, positive
   topological-prefix coordinates preserve its compute order; sorting affine
   coordinates across components is therefore topological. For resource word,
   insert the M and V FIFO edges and topologically sort before lowering to
   singleton subgraphs. Official Q2 still inserts COPY and memory dependencies;
   compute order preservation is not complete execution equivalence.
2. **Ideal resource bound.** For m homogeneous M(a)-V(b)-M(a) jobs, each pipe has
   one slot and 0<b<=2a. M work gives 2am <= optimal. Pro2's explicit word with
   h=1+ceil(b/a) has a feasible ideal schedule by 2a(m+1); its finite m=1,2
   cases also fit. This upper bound assumes no COPY, spill, finite capacity or
   cross-core delays. It is never used as an official-score acceptance test.
3. **Official lower bound.** A successful four-core solution must execute every
   original M/V operation. Sum of cycles of each such pipe divided by four is a
   valid resource lower bound (schedule_step3 PIPE_SLOTS=1 and _op_duration).
   The compute-only critical path is another relaxation. Step3 local_makespan
   is not a valid general global lower bound. The provided graphs use integer
   durations, permitting an integer ceiling of the total-work bound.
4. **Coverage.** Our fresh 100-graph static scan matched the guarded resource-word
   template only at 008,084,095, consistent with the Pro2 report. Sixteen graphs
   have one compute component. Neither statistic is a success-rate estimate;
   no extra evaluation was run by this scan. Tensor topology/size/position are
   not checked by the compute template and can invalidate performance intuition.
5. **Protection.** E0-confirmed strict improvement preserves quality relative to
   this run's confirmed seed. It does not prove a fast end-to-end solver, beat
   every historical plan, solve all cases, preserve k-to-k scores, or guarantee
   official success on every input. Four mock controller fault tests cover
   errors/timeouts/ties/no-success without executing a real E0.

The six development examples and board selection are deliberately exposed;
future coverage tests must identify their different role instead of calling
these six a holdout. Existing 008 evidence being near its resource bound means
transfer and lower solver cost are more promising than tuning 008 indefinitely.

Reproduction (static, zero evaluators):

```sh
.venv/bin/python -B -m src.q2_nikolastarx.static_analysis data/raw/a/official/data --cores 4 --output NEW_STATIC_JSON
.venv/bin/python -B -m unittest discover -s tests/q2_nikolastarx -p test_selection.py -v
```

`static-analysis.json` is the reproducible combined scan. `guard-domain.json` and
`compute-bounds.json` preserve the preceding exploratory scans with the same
Index and formulas; they are static diagnostics, not formal-case performance.
