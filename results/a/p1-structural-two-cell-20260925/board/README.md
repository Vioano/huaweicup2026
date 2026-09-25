# P1 structural two-cell result export

This package contains two successful case/5-core records from run `20260925T1056Z-s6607-structural-two`: case 016 (Makespan 2,941,234; solver 42.644752515 s; E0 31.892888094 s) and case 024 (Makespan 974,062; solver 11.674064057 s; E0 6.045528421 s). Both selected `intact-root-heavy-fused`. This is a partial 2/500 result, not a full-matrix score.

`board-feed-20260925T1056Z-structural-two.json` references the compressed plan/result/trace, per-cell derived run receipts, official logs, and exact copied single-core baselines. `run-1056Z/evidence.tar.gz` preserves the original remote archive; all 33 manifested payload files are also preserved under `run-1056Z/raw/`. `run-1056Z/controller-run.public.json` is an explicitly path-scrubbed derivative; the unmodified local controller receipt remains at the original runtime output path.

The preflight used the main-repository validator from the worktree root and returned `valid: true`, `eligible: 2`, `records: 2`. It checked format and available bytes only; it did not execute solver/evaluator or write to the central board. Machine OS release, CPU, GPU, RAM, per-run peak RSS, random seed, and OS cache state were not recorded.
