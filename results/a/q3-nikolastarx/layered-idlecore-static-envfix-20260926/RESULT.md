# Idle-core static probe result

The corrected `PYTHONPATH=.` launch reached the code. The synthetic `r=4, K=1..4` comparison against the original committed `partition_tracks` returned identical groups and metadata for all four values. This is a small regression sample, not proof for every `r>=K` input.

The one permitted 068/K5 `construct_layered` call passed track partitioning and priority construction but raised `GuardError: selected direct construction exceeds no-spill frontier guard; no search/retry` at `layered_query_flow.py:474`. The frozen first-exception rule stopped execution. Thus 088/K5 was not called, `derive_multicore_plan` was not called, and there is no plan hash, per-core M/V report, path `Ldelta`, official legality finding, or score. The guard result is specific to this direct R9 construction and capacity; it does not show the original graph is infeasible.

Exact calls: 1 pure constructor; 0 `derive_multicore_plan`; 0 Task, Step, E0/E1/E2; 0 retries. [receipt.json](receipt.json) contains the frozen call ledger. The old failed import run remains untouched. The edited source SHA-256 was `78e1fd656b479399c42eaccd4d7cf9a5dffc8f77abdb5c2929ff117f388936f5`; no source edit was made in this follow-up.
