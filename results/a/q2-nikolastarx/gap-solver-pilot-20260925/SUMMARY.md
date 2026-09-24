# Gap solver pilot audit

Four targeted coordinates only. Baseline attempt 0 native record matches pinned baseline truth on M, five movement fields, and cross-task traffic. The selected full raw plan SHA matches the solver ledger; its canonical SHA binds to the selected attempt. Selection is the lexicographic minimum of complete baseline and candidate attempt scores. At 008, the candidate was worse and baseline was retained after two native E2 calls, not a zero-call test. The unselected candidate plan bytes were not retained, so its canonical hash is recorded but cannot be independently recomputed from plan bytes.

| Case/k | Selection | Baseline M | Candidate attempt M | Selected M | Baseline → candidate extra DDR (B) | Solver process wall s | Internal solver wall s | External E0 wall s |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 003/k2 | candidate | 511949 | 248166 | 248166 | 98304 → 5067158 | 5.058 | 4.879 | 3.369 |
| 005/k3 | candidate | 80167 | 49426 | 49426 | 3101386 → 2394028 | 1.738 | 1.566 | 0.715 |
| 056/k5 | candidate | 253392 | 96280 | 96280 | 0 → 4863236 | 3.837 | 3.635 | 1.692 |
| 008/k5 | baseline | 52291 | 233682 | 52291 | 0 → 11172480 | 0.927 | 0.757 | 0.251 |

All 8 processes exited 0, left no surviving PIDs, and have no in-flight work. Totals: 4 solver processes, 8 native E2 records, 0 fallback, 4 independent E0. Solver and external E0 clocks are separate. This is not a full algorithm score or an isolated time-budget experiment; constructor wall is not claimed. Online directory contained no standalone plan JSON to archive. Archive hashes and mtime-zero roundtrips are in archive-manifest.json.
