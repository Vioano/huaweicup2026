# Q3 band-lookahead full500: execution guidance

**State: prepared only. No solver or official E0 was started.** The ten manifests describe one frozen algorithm at solver commit `7773fed30433f0b1487f34962a4034224d5796cf`, entrypoint `src.q3.band_lookahead_solve`, algorithm ID `q3-band-lookahead-structure`, producer session `nikolastarx/s-3172f7b01b604cfb90aefd6396bd87bc`. Each shard owns 50 unique `(case 001..100, cores 1..5)` coordinates. The validator confirms exactly 500 unique coordinates, no gaps/overlap, 150 reserved E0 per shard, and schema validity for all ten files.

## Before any dispatch

The manifests are frozen for a future approved run. Resource admission is still pending: four workers is only a ceiling suggestion. Check active local benchmark load, CPU and memory first; set the actual host/runtime identity before execution and do not exceed four workers. If the available slot count cannot finish the chosen shard waves inside 3,600 seconds, leave remaining shards undispatched rather than extending the global deadline. Use the existing `src.q3.feedback_benchmark` runner per shard and an external coordinator for the ten processes; do not build a new dispatcher. Each runner invocation has the manifest's 900-second shard deadline and preserves its stop-on-first-failure behavior. The coordinator must enforce one absolute 3,600-second wall deadline across all shard invocations, at most 1,500 E0 reservations total, and no retry. Four admitted workers imply waves of 4, 4, and 2 shards; actual time, queueing and concurrency must be recorded. Never start duplicate shard run IDs.

Before the first process, verify the source checkout still matches the pinned commit and frozen raw inputs/config/E0 hashes, then capture the exact runner commit and argv. The manifests use unique run IDs ending `-s01` through `-s10`; store each runer's output under a distinct Q3 result directory. Existing untracked result directories in the worktree must be left untouched. The manifests' `runtime_id` explicitly marks resource admission pending; resolve it to the actual runtime identity before dispatch by regenerating/revalidating the manifests and recording new hashes, or stop until that can be done. Do not silently run with the placeholder.

## Evidence and timing

Each cell is a fresh solver process and starts from a fresh forest incumbent. It may make at most three online E0 calls total: incumbent construction/validation plus at most one band-DP/single-leaf-lookahead proposal. The proposal replaces the incumbent only on a strictly smaller official Makespan. No old plan or score fills a coordinate. Keep successes, failures, timeouts and undispatched cells visible; zero retries.

Report full solver child wall time per cell, covering input read through plan write and including any online E0 candidate calls. Keep runner setup, queue/wave delay, result validation and archive/export time as separate batch overhead. Also report offline mechanism and policy-check time separately; do not add those durations to a cell solver time or count offline E0 as an online call. The coordinator reports actual worker count and shared-host conditions. Parallel throughput is a batch scheduling result, not a per-cell latency improvement.

The reported prior offline evidence is 7 E0 for single-leaf mechanism evidence, 45 new E0 plus 2 exact historical reuses for a complete 50-family, and 6 policy/static checks. The root session's five fresh integration cases completed with 5 solvers/12 online E0 in49.291143s; they remain separate from this unstarted full500 batch. These figures remain separate from the fresh 500-cell batch.

## Same-plan P2 boundary

This manifest set is P3 only. It does not authorize extra E0 work for P2 comparisons. A later same-plan P2 comparison needs its own explicit budget and run manifest. An existing P2 artifact may be cited only after exact graph, config, official evaluator, core count and plan bytes are matched; record its historical source and timing. Do not compare different plans and call that a same-plan Cache effect, and do not include P2 calls in the 1,500-call P3 reservation.

## Current resource decision

The coordinator has deferred both P2 and P3 new long batches while the old P2 PID76786 remains live and swap is high. No full500 shard has been launched. Four workers is not admitted. After the old process ends, recheck pressure and admit at most one long batch, starting with one worker and considering two only after measurement. This is resource sequencing, not pausing the P3 research goal. Same-plan P2 is already within the user-authorized research scope, but needs a separately frozen finite budget; these P3 manifests reserve no P2 calls.
