# R9F fifth-core construction: local static check

This is the last-round candidate derived from the completed R9 Pro answer. It
uses the repository's frozen graph validation, attention recognition, and
priority helpers. The submitted interface is still exactly the two required
plan fields. No Task, Step, P2, P3, or E0 evaluation ran in this phase.

`probe.py` fixes the previously recognized four-track coverage set
031/035/064/068/088 and applies one case-independent rule. The frozen original
graph archive, config and constructor file hashes are embedded in `run.json`.
Run with:

```
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python results/a/q3-nikolastarx/r9f-final-static-20260926/probe.py
```

The initial bare invocation omitted `PYTHONPATH=.` and failed at import before
reading any case. The corrected invocation completed. Unit tests in
`tests/q3/test_fifth_core_contiguous.py` passed 3/3.

| Case | Static result | Fifth-core UB peak | Plan SHA-256 prefix |
| --- | --- | ---: | --- |
| 031 | rejected by bucket capacity guard | — | — |
| 035 | passed | 81,920 B | `65eeff5b` |
| 064 | passed | 0 B | `ef015430` |
| 068 | passed; exact Pro plan replay | 90,112 B | `ee8364e7` |
| 088 | passed | 40,960 B | `ba6a5fe7` |

For 068, official `validate_graph` accepted the original bytes and the frozen
repository `RawIndex` and Pro helper yielded identical compute ops, predecessor
sets, successor sets and topological order (5,351 ops). Their sole `RawIndex`
AST difference is the repository's extra original-graph validation guard; the
Pro helper's `helper_AST_identity.json` compares an older prototype and must
not be read as identity with the current repository source.

The 068 plan SHA-256 is exactly
`ee8364e769437cb226cbe95cde845c0bbea59b2fd4e84dc47806d517949b323b`.
This reproduces a static certificate, not an official score. Real Task COPY
placement, Step2 spill, Step3 memory reuse/FIFO, P3 makespan and same-plan P2
remain untested.

The four supported graphs have a combined **optimistic** upper bound of only
`+0.1176445340` on the 100-case K5 mean if all other graphs remain unchanged,
using the independently archived compute-only lower bounds. Even at that
unrealistically favorable bound, the old fixed solver's 4.7576166788 mean
would reach at most about 4.8753. This family is a mechanism test and possible
incremental improvement, not a complete route to the user's >5 target.
