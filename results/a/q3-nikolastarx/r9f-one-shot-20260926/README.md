# R9F 068/K5 frozen official diagnostic request

This package is a proposed **single** Task/Step/P3 and conditional same-plan
P2 window. It has not been admitted or executed. The candidate comes from the
completed R9 Pro answer and was independently replayed by the repository's
static constructor. Its exact two-field plan SHA-256 is
`ee8364e769437cb226cbe95cde845c0bbea59b2fd4e84dc47806d517949b323b`.
Static UB peak 90,112 B is not an official legality or Makespan result.

`prepare_control.py` copied three pre-existing official control artifacts by
content hash from the central score board's local blob store, without scoring.
The exact old Forest500 plan SHA-256 is `955cfb794f0c82641b6d4c1411591c77dafc0458a2c1731184fee809aef16ff1`;
its P3 result is 116,345 cycles and its same-plan P2 result is 131,631 cycles.
`old_control.json` SHA-256 is
`fc3ccd32cb89398fcf35b8d6d622e2e9336ab026fdc8fff8f0cac07054777d38`.
The immutable old plan and result bytes are in `control/`; the control file
cross-checks their hashes, graph/config/official identities and the saved board
snapshot and pair manifest. The central store was read only.

Source must be frozen at a committed SHA. `src/q3/r9f_one_shot.py` verifies
the full HEAD, official input/source manifest, its own file SHA, the candidate
plan bytes, admission file SHA and old control before creating an output dir.
Run only in a clean isolated checkout of that SHA. An unrelated untracked
`src/*.py` also causes the source guard to reject.

The only requested budget is 068/K5: at most one P3, then one P2 **only if**
P3 is strictly below 116,345 and all prepared guards pass. Each P3/P2
preparation has five Step1, five Step2, five prepareStep3 and five Step3
simulation calls; Task3/Task2 at most one apiece. The runner charges calls at
function entry, saves complete prepared data and counts, checks actual COPY,
spill, FIFO, MEMORY_REUSE and combined graph via the six-layer prepared guard,
then records official results. One worker, 90 seconds per phase, 600 seconds
total, stop on first anomaly, zero retries. Guard failure consumes the P3 slot
and prevents P2. This is a diagnostic process, so `solver_wall_seconds` stays
null; its measured wall is labeled diagnostic, not final algorithm time.

Acceptance against this exact control requires `M3_new < 116345`,
`M2_new <= 131631`, and exact rational `M2_new/M3_new >= 131631/116345`.
Bytes moved and hit rate are recorded separately. No case result may be
spliced into the old fixed solver's 500-cell score. If this one-shot supports
the mechanism, freeze a **new case-independent selector** and run a separate
whole 100-case × five-core-count benchmark for the final algorithm as the
user requested. All its online selection and paired calls must be included
in each cold solver wall. If the candidate fails, retain the negative result
and use the best already fully validated fixed solver as the paper baseline.

After the coordinator issues a new concrete admission and the clean source
checkout is verified, the command template is:

```
python3 -B -m src.q3.r9f_one_shot \
  results/a/q3-nikolastarx/r9f-one-shot-20260926/candidate \
  results/a/q3-nikolastarx/r9f-one-shot-20260926/run \
  --source SOURCE_COMMIT --source-sha256 RUNNER_SHA256 \
  --plan-sha256 ee8364e769437cb226cbe95cde845c0bbea59b2fd4e84dc47806d517949b323b \
  --admission-file ADMISSION_PATH --admission-sha256 ADMISSION_SHA256 \
  --control results/a/q3-nikolastarx/r9f-one-shot-20260926/old_control.json \
  --control-sha256 fc3ccd32cb89398fcf35b8d6d622e2e9336ab026fdc8fff8f0cac07054777d38
```

No old 044, 071 or R9 experiment budget is reused by this request. The
coordinator owns resource exclusivity and admission; simply having this
package or a prior conditional allowance never authorizes launch.
