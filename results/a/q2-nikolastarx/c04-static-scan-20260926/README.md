# C04 score-free official-graph coverage

The fixed width-32 C04 adapter was run once on all 100 original graphs × 1–5 cores. It returned plans passing its structural, physical COPY-byte and zero-spill interval guards for 52/48/58/62/66 graphs at K1–5 respectively: 286 of 500 cells. The remaining 214 cells abstained because the bounded ready window had no memory/work-admissible pair. An abstention is not a proof of graph infeasibility.

Command: `uv run python -B scripts/q2_c04_static_scan.py`. Completed construction/guard time summed over cells was 135.941195 seconds on the shared macOS host; this is in-process static screening, not cold solver or official benchmark timing. The source and raw input/config hashes and every outcome are in `summary.json`.

No E0, E1 or E2 was invoked. These guards do not establish official Step3 legality or Makespan gains. In particular, 044 and 090 abstain at K5, so the earlier 044 success belongs to the different stationary-job constructor and cannot be attributed to C04.

The next six-cell mechanism falsification is frozen in `../c04-six-pilot-preparation-20260926/`. This screening examined all public cases; the selected pilot is targeted and is not a blind holdout or a full500 result.
