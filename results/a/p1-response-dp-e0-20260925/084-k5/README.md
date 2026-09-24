# P1 case 084, k=5: cached-full candidate with independent E0

This archive combines the saved cached-full ordered-graph constructor receipt with one independent official E0 evaluation of the same plan. The constructor used `q1-packet-dp`, variant `cached-full-ordered-graph`, source commit `59aee1fa1b5df8795de158dcc96ea160663efbe2`; its receipt records 3.6180724169826135 seconds. E0 ran separately and took 1.9712685419945046 seconds. Combined call accounting is one constructor, one E0, zero E1/E2, zero retries; this was not one same-process run.

E0 result: Makespan 397542 cycles, scheduled DDR 22175850 bytes, extra DDR 8939520 bytes, spill 0. These are for this cell only and do not establish a new unified full-matrix score. The diagnostic checks the selected final plan; it does not establish equivalence for unselected edges or global optimality.

`result.json.gz` and `trace.json.gz` are full byte-preserving gzip copies; `manifest.json` records both compressed and decompressed hashes. The raw result, trace, input, original E0 receipt and official log remain local and are excluded from the feed artifacts. `public-run.json` is derived from the original receipt; it replaces only the absolute Python executable path and adds the independently sourced constructor stage. The original `receipt.json` is untouched.

The plan artifact reuses the existing cached-full static plan at `results/a/p1-response-dp-static-20260925/cached-full/plan.json`; its SHA matches the plan used by E0 and the three-state plan. The baseline gzip was copied byte-for-byte from the fixed source feed commit recorded in the manifest because its original path is not present in this worktree.

## Submission preflight

The project `protocol.py --submission` check passed against this worktree: `valid: true`, `submission: true`, `records: 1`, `eligible: 1`; no solver/evaluator or production service was invoked.
