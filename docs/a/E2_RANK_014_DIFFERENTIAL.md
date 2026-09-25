# Queued 014/K1 rank-index preparation differential

This is a **single new preparation**, with no E0 or native replay. It compares
the private E2 rank-index candidate at
`5f3c1f536dc9c63aefdbc1762fbd023e8a6aea57` against the already saved
prepared object from frozen E2 `603b0741e21c449d3db652ebd67c94f2dc014cc9`.
The fixed old run is at
`results/a/q2-nikolastarx/preparation-profile-20260925/run/results.zip`
in commit `e4f7b13e4af04914a1264a650831a3959f14a373` (ZIP SHA-256
`bdc28f73c3001ec4385143a48a80538f1147067812471a1ddce6d9d4b13148ca`).
Its 014/K1 graph, selected plan, config and 28,399,387-byte prepared snapshot
are reused; the old preparation is **not rerun**.

`scripts/q2_rank_prep_package.py` creates a capsule from those exact Git
objects. It carries the 51 required E2/official source files, the new runner,
locked dependencies, inputs and old result archive. It refuses any source
change beyond the rank optimization files. The capsule SHA printed by this
command must be fixed in the coordinator's dispatch before upload:

```sh
python3 scripts/q2_rank_prep_package.py output/e2-rank-014/capsule.zip
```

**Admission and resource limits:** wait for the coordinator's exclusive CPU
Standard Colab window. One worker, one new preparation, zero E0, zero native
library loads/replays, zero retries. Reserve the attempt before starting.
Use a 180-second external child watchdog plus the runner's 150-second alarm;
4 GiB address-space limit and external sampled process-tree RSS limit;
64 MiB per output file, 32 MiB prepared-object cap. Keep an independent
10-minute runtime termination guard. Environment setup and transfer time are
reported separately. On failure, timeout or uncertain identity, stop without
retry and preserve partial artifacts. Stop the VM and read back that no
sessions remain after collecting output.

In the admitted Linux session, verify the exact capsule SHA, unpack to a fresh
directory, then run in its root using the locked Python 3.12 environment:

```sh
uv sync --locked
timeout --signal=TERM --kill-after=2s 180s \
  .venv/bin/python -B q2_rank_prep_differential.py . /path/outside-capsule/new-output
```

The runner hashes all capsule files, checks the old archive and prepared-object
hash, and guards E0/native entry points. It performs the same private Step3
optimization as the old profile, then applies the new rank-index patch. It
runs only `_build_scene_b_tasks`, `validate_execution` and `_native_b.pack`.
The full `(tasks, cross_links, traffic, movement, plan_view)` snapshot is
compared against the old one by pickle bytes and recursive field/value/order;
summary counts are checked separately. New `prepared.pickle`, report and
process/VM receipts are retained. Any mismatch is a failed differential, not
an accepted optimization. The old pickle is SHA-checked and scanned to reject
executable pickle opcodes before loading.

The old 52.521-second preparation was measured under `cProfile`, so its wall
time is diagnostic and **not** a controlled unprofiled speed baseline. The
new run establishes preparation equivalence and one new wall time; a later
speed claim needs matched unprofiled conditions and separate authorization.
