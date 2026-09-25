# Unattempted-only completion segment (proposal; zero new scoring)

The original run ended naturally at its unchanged 3,600-second wall limit:
`stopped_before_dispatch`, 400 successful cells, 788 actual E0 calls, zero
failed/timed-out cells. Original T0/T1 are 2026-09-25 19:27:41.032041Z /
20:27:43.746843Z. The pilot-to-expansion review wait remains in that wall time.
The 400 records and their call ledger must never be restarted or rewritten.

`manifest-completion-100-proposed.json` copies, without editing, exactly the
100 unattempted job objects from the frozen expansion manifest. Its new run ID
is `q3-r9f-final-full500-completion100-20260926-s3172`; its stage is
`completion-100`. Solver `f6fd8153375a7fb64f9af2c8f36c35356fb7d878` and runner
`65c07e062ed9be78dda32ef4bb58a9891f373de9`, input identities, parameters,
per-cell call caps, one worker, and zero retries remain fixed.

The proposed second segment has a separate 1,200-second wall budget and a
90-second per-cell ceiling. It reserves at most 363 E0 calls. Together with
the already spent 788, the maximum combined expenditure is 1,151, below the
unchanged full-suite 1,800-call ceiling. The pinned runner still declares its
original 1,800 global ceiling; the exact finite job list and per-job bounds
provide the stricter 363-call bound for this segment. No other coordinates
or retries are authorized by this proposal.

Proposed command, only after a new coordinator gate and source/resource check,
in the existing clean execution checkout at the pinned runner commit:

```sh
python -B -m src.q3.fifth_core_full500_runner \
  results/a/q3-nikolastarx/r9f-final-full500-20260926/manifest-completion-100-proposed.json \
  results/a/q3-nikolastarx/r9f-final-full500-20260926/run-completion100-20260926-s3172 \
  --runner-commit 65c07e062ed9be78dda32ef4bb58a9891f373de9
```

This is a new run directory, without `--continue`. Stop at the first failed,
timed-out, invalid or ambiguous cell; retain all evidence and verify child
cleanup. Do not change the frozen solver or official evaluator. The output
directory must not exist at T0. Preparation and artifact audit invoke zero
new evaluators or solvers.

If both segments pass, report a disjoint 400+100 full matrix of one fixed
algorithm, retaining each original run ID, T0/T1 and wall budget. It was not
completed within the original one-hour run. The original segment shared the
host with the coordinator-admitted P2 run from 20:23:54.673461Z through
20:24:03.588371Z; no isolated-host timing claim is made. This split is neither
historical winner selection nor a new algorithm version.

Preparation details and hashes: `COMPLETION_PREPARATION.json`. Independent
readback of every prior successful record and the new no-score source
preflight: `SEGMENT1_READBACK.json` when present. Resource admission is
separate from this proposal.
