# R05 saved-plan pair — frozen, no dispatch

The experiment compares the exact saved 003/K2 seed with the raw candidate
recovered from the original R05 metadata. It tests whether the static proxy's
rejection agrees with official Makespan, and records all movement categories.
It is a mechanism experiment, not a new online solver score or a full100 mean.
The current c665 003/K2 result is 245150 cycles, retained only as a separate
existing comparator. Both frozen plans will be independently evaluated.

`prepared.json` pins the final **capsule-v3.zip** (517312 bytes), controller,
worker and manifest. Earlier local v1/v2 packages were never dispatched and
are retained. Root review corrected portable paths, worker import setup,
duplicate call accounting, and the actual Colab cell entry semantics.
Syntax, cell import without `__file__`, entry dispatch with kernel argv, and
independent extracted-capsule preflight passed; none executes an evaluator.

Budget: one CPU Standard VM, one worker, seed then recovered, at most two
official E0 calls; each attempt is reserved before dispatch. Each call has
180 seconds, batch work 360 seconds, sampled process-tree RSS 4 GiB, output
file limit 64 MiB, zero retries. No solver construction or E2 call. Failure
stops the pair and preserves original error/partial files. `output/batch.json`
is the authoritative call ledger. The controller's setup status is separate.
An independent 10-minute VM stop guard and the coordinator's explicit window
are required before creating a runtime.

Upload the capsule to `/content/q2-r05-pair-20260925.zip`. Execute
`scripts/q2_r05_pair_colab.py` through the existing CLI with
`P2_R05_PAIR_MODE=run` and `P2_R05_PAIR_SHA256` from prepared.json. Results are
`/content/q2-r05-pair-20260925-results.zip`; verify downloaded bytes/hash before
stopping and independently reading back the session list. An observation
timeout is not permission to redispatch. This protocol does not authorize any
additional case or a full500 batch.
