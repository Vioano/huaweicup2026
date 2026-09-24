# Prepared P2 gap archive watcher

The archive branch has an already pushed and enqueued immutable `shard-001-050` at `bbf42eff6d344c3f1c73f0461b1f05e99422b4b5`. The watcher records that fixed shard and never republishes it. For later accepted prefixes, it exports cells 51–450 in groups of 50, 451–495 in groups of 5, and 496–500 singly. Each shard is checked with the local board submission validator before the watcher stages only that shard, commits, pushes non-force to its own branch, and invokes the external sync CLI's `enqueue`. The sync service itself is not started or changed. A stopped scoring summary exports a remaining short accepted tail and then stops the watcher with failure. A missing scoring PID while the summary still says running also stops the watcher; the scoring process is never signalled.

Do not run before the root agent checks and releases this implementation. The eventual command must supply the real scoring summary, frozen manifest, archive output root and unique run identity, the known scoring PID `76786`, this branch, and explicit paths to the existing sync repository, Python, and config. The config is passed to the sync CLI; the watcher does not read it. Put `--journal` under this archive worktree's `output/` directory. The summary source reference is a portable label, not a local absolute path. Example shape:

```sh
python3 scripts/q2_gap_stream_publish.py \
  --summary /SCORING-WORKTREE/output/RUN/summary.json \
  --manifest /SCORING-WORKTREE/results/a/q2-nikolastarx/gap-full500-20260925/manifest.json \
  --output-root "$PWD/results/a/q2-nikolastarx/gap-full500-archive-20260924T2124Z-s59" \
  --journal "$PWD/output/q2-gap-stream-publisher.json" \
  --run-id p2-gap-full500-20260925-s59-20260924T2124Z \
  --source-reference p2-gap-full500-20260925-s59/20260924T2124Z-s59ee/summary.json \
  --expected-scoring-pid 76786 --branch codex/q2-gap-archive-s8ee \
  --producer-session nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894 \
  --task-url https://github.com/huaweibei123/huaweicup2026/issues/33 \
  --runtime-id ACTUAL-RUNTIME-ID \
  --sync-root /SYNC-REPO --sync-python /SYNC-PYTHON --sync-config /SYNC-CONFIG
```

The journal records each shard's last E0 UTC, export/commit/push/enqueue UTC, fixed commit SHA, enqueue delivery ID, and source snapshot. A nonblocking `fcntl` lock prevents two local watchers on the same journal. External commands have a 120-second timeout; command failure stops the watcher without touching scoring. Before commit on macOS, the watcher runs `dot_clean` only on the new shard and scans it for residual AppleDouble or `.DS_Store` files. It also checks committed exporter/publisher bytes against HEAD and refuses unrelated staged files. A failure leaves all evidence intact; there is no automatic retry, restart, re-score, or central acceptance claim. Restart needs operator review of the journal and on-disk commit. Already committed shards are recovered by `git log -1 -- <shard path>`; a repeated push of the same commit and enqueue of the same fixed feed are idempotent. The first 50 are never recommitted or resent.

Offline fixture evidence: `tests/test_q2_gap_stream_publish.py` checks the schedule and simulates an interruption at push using a complete mocked command layer. One commit, two push attempts, and one enqueue occur across interruption and resume; a third call performs no commands. `python3` direct function execution passed (system Python lacked pytest). The exporter separately processed four real pilot plan/result/process/ledger originals in disposable directories using an explicitly synthetic reordered 500-row manifest: four fixture rows passed `protocol.py --submission` local validation, and an overlapping range was rejected. These four fixture rows are neither a new full500 run nor a real delivery. No real Git mutation, network, enqueue, solver, or evaluator was invoked during these tests.
