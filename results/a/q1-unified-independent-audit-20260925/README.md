# Unified P1 full500 read-only audit

Frozen algorithm: `48faef6f1386c3dc7d037674a38af29d533ba774`.
Runner: `43dc7a89d2b5afe328ba6a9c576463e0549f7275`.
Run: `20260924T1810Z-s59ee`; completed 2026-09-24T18:16:09.908Z.

The root independently read all 500 original plans, E0 results, diagnostics,
and run receipts, plus all 100 frozen official single-core denominators.
It checked original plan/result/diagnostic hashes, compressed and raw baseline
result hashes, graph/config/official-code identities, output keys/core counts,
selected plan hashes, makespan and full movement equality, successful statuses,
call counts and recorded owned-process cleanup. This is an independent
read-only audit of actual artifacts, not a second execution.

All 500 passed. The 244 selected candidates that had online E1 scores matched
external E0 in makespan and the complete movement object. The remaining 256
had one distinct plan and zero E1 calls. There were 586 E1 calls total.
The fixed source uses graph-derived construction and online scores; no
historical best-cell selector participates in its algorithm.

Five-core arithmetic mean speedup is **3.9875190662504423**, above 3.85.
See `summary.json` for 1–5 core means. The denominator is the original official
single-core output, not this solver's k=1 output. This milestone is one unified
algorithm over all 100 graphs at all five core counts.

Solver wall time includes cold interpreter startup, input, all constructions,
online E1, serialization and worker cleanup: median 0.549630875 s,
nearest-rank P95 10.113750583 s, max 21.700526583 s. External E0 is separate,
max 115.620735458 s. Batch wall 425.8197395 s used a 2→4→8 worker ramp on Apple
M5 Pro, macOS 27, Python 3.12.13. These are concurrent-batch measurements,
not isolated-machine latency or true hardware acceleration.

The official validator permits spills: 136 cells had nonzero spill bytes.
No global optimality or full-domain E1 equivalence is claimed. The production
owner publishes immutable raw evidence and a standard feed separately; this
small audit is not a substitute for those originals. CPU rusage differences
under concurrent execution are not used as per-cell CPU timing.
