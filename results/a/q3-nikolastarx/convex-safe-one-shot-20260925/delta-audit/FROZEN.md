# Official P3 timeline delta, 005/K5

This is one read-only comparison of the already saved R9 and convex-safe official P3 traces. It does not invoke the solver, Task/Step, or E0. It does not infer a critical causal path from coincident event times.

- Old gzip SHA-256: `3c51fac6f14a7c2fdafad3eef6694fb8f38d473e00534c25cd4dadff13cfa0d8`.
- New gzip SHA-256: `385b30788297034a655329507f88ea0a3295d3d3d4f383c24f9c4c2952eb2ce0`.
- Script SHA-256: `84e8b4cbc67bdc78bbbed9323715318644da982dca84566c473c2a222b325c63`.
- Command from worktree root: `python3 -B results/a/q3-nikolastarx/convex-safe-one-shot-20260925/delta-audit/analyze.py`.
- Budget: one local process, 30 seconds, no retry; stop on any error. Output: `readback.json` and `stderr.txt`.
