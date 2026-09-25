# Fixed bidirectional full500 production package

Preparation only: no new full500 solver or evaluator has run. Formal P2 remains c66559a6, K5 mean 4.549756996698352.

The algorithm is `src.q2_nikolastarx.adaptive_bidirectional_guarded` at **15d86e13b4a8abb4bce445ac241aecac13f553bf**, in a separate unchanged checkout. One rule for all 100 graphs × 1–5 cores: construct the forward incumbent and at most one reverse proposal, compare complete plans online, minimize `(Makespan, added DDR bytes)`. Retain all input proposals before scoring. No graph-ID selection and no historical winner mixing. Same-M DDR improvement is a tie-breaker; smaller M can increase DDR.

The producer is `scripts/q2_bidirectional_local_full500.py`, with outer `scripts/q2_bidirectional_full500_supervise.py`. The fixed manifest contains 500 ordered coordinates (K5 first, then K1–K4), 77 source/official file hashes, 111 official input/code hashes, 51 E2 source/native hashes and interpreter identity. The single-core baseline is report-only, resolved relative to the manifest. Local read-only preflight and bounded fake-process tests passed; see receipts. E2 is pinned at 603b0741e21c449d3db652ebd67c94f2dc014cc9. Final official E0 code is unchanged.

## Frozen scope

- Two workers; 500 cold solver starts; no more than 4 distinct E2 API starts per cell / 2000 total, 500 external E0 starts, and a reserve of at most 2 possible fallback calls. First fallback, unknown result or failure stops new dispatch. Only already-dispatched cells can settle. No retries.
- Per solver and external E0: 180 seconds and 2 GiB observed process-tree RSS. Outer budget: 7200 seconds including identity preflight, 4 GiB tree plus observer RSS. Preserve every failed/in-flight record.
- Observe output growth at 20 GiB and free disk reserve at 10 GiB; exceeding either stops the tree. These are sampled thresholds, not hard OS quotas. Normal polling is one second; traversal and scheduling can add delay.
- Whole-run completion requires exit 0, 500 accepted unique coordinates, native-versus-E0 metric equality where native was used, all persisted candidate originals, no in-flight calls and no surviving known scorer processes. Zero-E2 single-plan routes receive independent E0. Native checks include M, all five movement-byte fields and cross-task traffic.

The outer supervisor uses fixed-source process ancestry and PID birth identity. Detached descendants observed before termination are tracked. A process born and orphaned between samples may escape observation; persistent ps/cleanup failure is reported uncertain, never as successful cleanup. All timings are from two workers on a shared Mac, not exclusive-host latency or actual accelerator timing. Solver wall includes online selection and source checks; independent final E0 is separate.

## Reproduction

Use the Python 3.12 interpreter with the manifest executable hash, a clean source checkout at 15d, the original official input directory and the pinned Mac E2 export. After a separately issued resource admission gate, run the outer supervisor with explicit `--repo`, `--python`, `--runner`, `--manifest`, `--raw-root`, `--e2-root`, `--gate` and a fresh `--output` parent. Producer results are under `results/`; outer logs and receipt are siblings. The gate must pin source, runner, supervisor and manifest. This package supplies no admitted gate.

Mac was chosen from actual prior evidence: the earlier c665 full500 completed with solver maximum 40.187 seconds; a Colab full500 stopped at its 67th start because E2 preparation exceeded 180 seconds. This is a resource decision, not a claim that all Colab execution is slower. No cloud VM was created for this package.
