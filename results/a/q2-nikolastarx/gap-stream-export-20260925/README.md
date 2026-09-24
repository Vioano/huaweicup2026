# Gap full500 streaming board export (prepared only)

`scripts/q2_gap_stream_export.py` is a read-only consumer of the frozen `gap_full500.py` run. It never starts a solver, E0, E1, or E2. It reads one `summary.json` byte snapshot, takes only the contiguous `accepted` prefix, checks each accepted row against its raw plan, result, solver/E0 process receipts, and online ledger, and writes a new immutable board-submission-v1 feed and archived evidence for one 50-cell shard. A shorter final shard requires `--final` and a terminated summary. Existing archive bytes must match; a changed file is rejected. The first summary snapshot SHA is retained in `snapshot.json`; later idempotent exports preserve that snapshot as the live summary grows.

Example after scheduling release and after the first 50 accepted cells (replace the unique run and output paths with actual ones):

```sh
python3 scripts/q2_gap_stream_export.py \
  --summary output/ACTUAL-RUN/summary.json \
  --manifest results/a/q2-nikolastarx/gap-full500-20260925/manifest.json \
  --output-root results/a/q2-nikolastarx/gap-full500-archive-ACTUAL-RUN \
  --run-id nikolastarx-q2-gap-full500-ACTUAL-RUN --shard 0 \
  --producer-session nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894 \
  --task-url https://github.com/huaweibei123/huaweicup2026/issues/33 \
  --runtime-id macos-arm64-fresh-gap-full500 \
  --source-reference scoring-run/ACTUAL-RUN/summary.json
```

`--shard 1` emits cells 51–100, and so on through shard 9. One `(run_id, case, cores)` yields one attempt ID. The final E0 result gives the score; online E2 calls stay inside the solver wall time. The denominator is the fixed 60afc38 official single-core E0 reference, never the old P2 solver Makespan. Only 500 accepted cells support a full-algorithm average. A failed run retains its original failures separately; this exporter currently emits accepted cells only. No feed is pushed or enqueued here. The root agent must check the generated feed and archived refs with `src/benchmark_board/protocol.py --submission`, then commit those bytes in a separate archive worktree before any handoff.

`--source-reference` is an explicit portable label; the scoring worktree need not sit inside the archive worktree. The summary snapshot SHA is stored separately. The schema's `code_source` permits only repo, commit, path, and entrypoint, so no unsupported `sha256` field is added. Upstream references identify Fang's P2 gap packet and P3 gap calendar source at their fixed commits.

Protocol read: `/Users/nikolastar/Projects/huaweicup2026/docs/benchmarks/SUBMISSION_PROTOCOL.md`, schema `/Users/nikolastar/Projects/huaweicup2026/docs/benchmarks/board-feed.schema.json`, reference implementation `/Users/nikolastar/Projects/huaweicup2026/src/q3/board_export.py`; the current worktree has the same validator entrypoint at `src/benchmark_board/protocol.py`. A four-cell pilot fixture passed end-to-end archive/validator checks but uses a synthetic summary and reordered manifest, and is never an actual full500 submission. No real 50-cell shard has been exported or validated.
