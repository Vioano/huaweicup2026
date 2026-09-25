# Q3 partial-preload Linux mechanism receipt

This receipt contains exactly three new official E0 attempts for case 044, five cores: candidate P3, same-plan candidate P2, and control-plan P2. It is a mechanism experiment, not a full-500 result.

- Candidate P3 Makespan: **37060** cycles; reused full-prefix P3: **38024** cycles, a reduction of **964 (2.5352%)**. Candidate G = 37060/37060 = **1.0**; control G = 38024/38024 = **1.0**. The prior P3 is exact reused evidence (SHA `d4cdf8dbabe22923b9a74329741fb39e74a588e619d9f101db1fd28ecd629da1`) and is not represented as a new attempt.
- All three new results report 140800 added bytes and 0 spill bytes. Candidate P3 has 11 hits / 182 accesses, 11264 hit bytes, 1012064 miss bytes, byte hit rate 0.0110072235; same-plan P2 provides the paired non-cache result.
- `solver_wall_seconds` is `null`/unknown. The 7.9257 s prepare diagnostic and score/host diagnostics are not solver wall time. `full500=false`.
- One prepare plus three E0 calls were made; no E1/E2, retry, or new full-prefix P3 call. Phase and per-core evidence remain in raw receipts.
- Candidate plan SHA: `0a75e3613ad5f69e293e45e6c1cfc1545b3b1036245ebc7bf0af75b3321df0fd`. Control plan SHA: `13914b24c18b59366be17de86a26d227ff85427cb00b184799587777547a6508`. The retained old P3 result uses the same control plan. Official single-core baseline SHA: `73f1d15fdea4f706b22099d2339a0e74a76c4114a68672077a98a8e15faa913c`. Source commit: `817e9e399f5efaf66cea6ddc495fe444950e43f2`; controller commit: `f4bc0b983f247e3395394e9b4ac25b25fd210d0b`; host checkout HEAD was `ff6e16ea8fbc2af90417aa045c457f37f6e167d7`.
- T0/guard READY was observed at `2026-09-25T06:08:27Z`; exact UTC start is not recorded by the controller (its deadline is monotonic). Preflight receipt was captured at `2026-09-25T06:08:16.647041+00:00`. Controller wall 57.15144412498921 s; stop `confirmed_empty`, watchdog `disarmed_by_confirmed_parent`, and fresh sessions-after exact empty rc 0.
- Evidence archive SHA: `02fa71024fcc6fe35071c7dd9e8a5516caa55609bcbb8fa930bcc661aa114898`; transport package SHA: `5b293299544502de4c5aa2569d55ebd768262d5462ea54f4f68092749445c6f7`. Original result gzip bytes were copied without recompression and verified against each worker `result_sha256`.
- Independent identity/FIFO audit: `results/a/q3-nikolastarx/partial-preload-linux-20260925T0603Z/INDEPENDENT_AUDIT.json`. It reports timing deltas consistent with earlier downstream starts; it does not prove complete causal decomposition.
- Protocol preflight: exit `0`, eligible `3`. See `protocol-preflight.json` for the actual command and output.

The exporter copies exact source bytes, verifies archive/member safety and hashes, generates public run projections without the local admission path, runs the read-only submission preflight, and records its real result. It does not execute a solver or evaluator.
