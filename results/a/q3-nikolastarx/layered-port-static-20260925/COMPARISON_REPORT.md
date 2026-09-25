# R9 layered port static reproduction result

The single frozen runner completed both authorized one-shot child constructions. Case 005 ran 0.25001729204086587 s; case 086 ran 0.37343800003873184 s. The outer interval was 2026-09-25T13:55:08.179947Z–13:55:08.817409Z. Both child processes exited 0; no exception, timeout, mismatch, or retry occurred.

For 005 the generated plan SHA-256 is `2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a`, equal to the frozen candidate SHA. Object equality, canonical JSON equality, and raw byte equality are all true. Canonical SHA-256 is `dd83571645ee9faa1256a19a6bb260e1981961f736f8ea0b1ead3cd397c8add5`.

For 086 the generated plan SHA-256 is `f2111af54fcc3c11048663db149a93290dbe4558e7d5b7eecf8ec49e847022e6`, equal to the frozen candidate SHA. Object equality, canonical JSON equality, and raw byte equality are all true. Canonical SHA-256 is `db577cc8ad8faa1efd4308b9eb5505e245bedf0d11f76656b56b3ae4088438ad`.

The official config parsers returned `capacity={"L1":524288,"UB":131072}` and `cross_delay_cycles=500`. Both metadata files identify `STATIC_CONSTRUCTED_NOT_OFFICIALLY_EVALUATED`; M2, M3 and G remain null. Total actual constructor calls: 2 (one each for 005 and 086). Total retries: 0. Task=0, Step=0, E0=0, E1=0, E2=0, `pipe_bound`=0. This records pure construction and byte-for-byte reproduction only; it is not official evaluation, official Makespan or complete solver timing.

`run_summary.json` contains each exact child argv, claims, timestamps, wall times, outputs, and call ledger. Per-case directories preserve candidate plan/metadata copies, constructed plan/metadata/evidence, stdout/stderr, and comparisons. `RESOURCE_PREFLIGHT.txt` retains the pre-run memory, load and process snapshot.
