# Response refinement pilot: 084/k5 and 080/k5

This is a two-cell pilot, not a full-matrix result. It used 2 solver calls, 8 E1 calls, 0 new E0, 0 E2, and 0 retries. Each cell used one worker. The solver timeout was 300 seconds per cell; the 660-second batch limit is an admission threshold, not a hard wall-clock cap, and cleanup can extend it.

| Cell | Solver wall (s) | Selected strategy | Plan SHA-256 | Reused E0 quality (cycles; scheduled / extra DDR; spill bytes) |
|---|---:|---|---|---|
| 084/k5 | 11.7018928750 | packet-dp-refinement | 5203ed797935cbf3777586247fa82191518485da839a6d680b150efb6ed5e3f6 | 397542; 22175850 / 8939520; 0 |
| 080/k5 | 0.5984056250 | fork-frontier | dd58e71b12af5274bcf0c7b2d360f0617875bd7e0ea221f73fc430882c1c0bdf | 97383; 5443584 / 3465216; 0 |

Both selected plans matched their prior E0 plan bytes exactly; each reused the already saved E0 result. No new final E0 was run. Full per-cell timings, calls, reuse sources, and hashes are in `cells/*/k5/run-public.json`; public diagnostics and plan files remain byte-identical originals. Prior raw E0 result JSON remains local; gzip copies are supplied with decompression hashes recorded in `manifest.json`.

The host was shared. At T0, the coordinator reported a P2 one-worker run still active; the observed system load averages were 9.33/10.91/11.02 and memory free percentage was 45%. These solver wall times are not exclusive-host performance claims.
