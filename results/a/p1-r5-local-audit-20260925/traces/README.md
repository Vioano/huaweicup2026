# Local read-only audit of archived author R5 traces

`whole_seed-audit.json` and `period7_seed-audit.json` are copies of the two
already completed pure trace checks. The checker's original run was not
repeated here. `interval-comparison.json` was produced once by
`src/review/p1_saved_trace_interval_audit.py` from the archived author trace
files, the copied audit JSON, and the archived author `diagnosis.json`. It
compares DDR busy union, core-0 M/V overlap and simultaneous idle intervals.

| Variant | Saved makespan | Observed-duration DAG | DDR busy union | Core-0 M/V overlap | Core-0 both idle |
| --- | ---: | ---: | ---: | ---: | ---: |
| whole_seed | 101836 | 101836 | 44604 | 0 | 2572 |
| period7_seed | 109412 | 109412 | 72324 | 7804 | 17952 |

All interval comparisons match the archived diagnosis, and the trace DAGs
show zero hidden start slack. This is a **local read-only audit of the author's
saved traces**. It is neither a local response-model reproduction nor an E0
evaluation. A matched observed-duration DAG does not validate fair DDR service;
DDR excess includes integer retirement effects and is not pure congestion.

Reproduce only the interval arithmetic with a new output path:

```sh
python3 src/review/p1_saved_trace_interval_audit.py \
  --audit-dir results/a/p1-r5-local-audit-20260925/traces \
  --output results/a/p1-r5-local-audit-20260925/traces/another-new-comparison.json
```
