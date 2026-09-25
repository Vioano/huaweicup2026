# Full500 runner validation

No new graph construction, Task compilation or evaluator was invoked for these checks. The frozen algorithm is still `834d8c957538ee069c66aadac9509552a4cc69d7`.

`stderr.raw` records the first five pure controller tests. `stderr-r2.raw` records six tests after recognizing the valid multicore single-candidate path. Tests cover fixed source identity, admission identity/budget/expiry, precise process dispatch accounting, official objective mismatch, zero-score single-core flow, and zero-score multicore sole-candidate identity. Command: `python -B -m unittest discover -s tests/q1 -p test_s6607_branch_full500.py -v`.

The full old v4 feed has **137 zero-E1 cells: 100 single-core and 37 multicore**. A unique candidate needs no online ranking. Rejecting every K>1 diagnostic without `selected_objective` would therefore incorrectly reject valid solver output.

`sole-candidate-replay/summary.json` records all 137 original diagnostic, plan and run hashes. Original diagnostics were read from the retained production run `20260924T1952Z-s59ee`; their hashes match its original run receipts, the run hashes match the notes in the published `0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297` feed, and original plan hashes match both sources. Compressed copies retain the exact original diagnostic bytes.

For each old zero-score output, root replayed the frozen response, structural and branch *control functions* with that existing plan and diagnostic injected as the baseline. The graph argument was `{}`; every graph constructor, recognizer, validator and scorer boundary was replaced by a function that raises immediately. All 137 returned the same plan, zero online score calls, and no selected online objective; the new runner accepted the precise sole-candidate identity chain. This is a pure controller replay with real old diagnostic inputs, **not 137 newly solved cases or official E0 evaluations**.

The actual full500 run must still produce a fresh plan and diagnostic for every cell. A zero-score path is allowed only when all retained parent/candidate plan hashes agree, there is exactly one unified candidate, all online ledgers are zero, and no refinement child/branch constructor ran. Independent E0, or strictly identity-matched prior E0 evidence, remains mandatory. All other missing or inconsistent online objectives fail.
