# Repair phase stopped at first R8 structure guard

The single frozen script process used `python3` and exited at `certificate.py:36`, while decomposing the first input, 005. R8's `_decompose` raised `UnsupportedStructure: one query row feeds a different query flow` at `src/q3/query_flow.py:111`. The original traceback is in `stderr.txt`; `stdout.txt` is empty. Case 086 was not entered. No subset expansion, DP result, five-core conclusion, plan, or official scoring took place.

This is a structure mismatch for the current R8 flow decomposition, not evidence that 005 or 086 is infeasible under the original problem or under another placement family. Per the frozen first-error/zero-retry rule, the script and its SHA were left unchanged and no second run was attempted. Calls to E0/E1/E2, Task, Step, solver, pipe_bound, `query_flow.construct`, and `Index.build`: zero.
