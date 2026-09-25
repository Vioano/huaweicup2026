# R9 005/K5 layered diagnostic supervisor — preparation only

`layered_supervisor.py` is a narrow adaptation of the previously used `query-flow-integration-20260925/integration_supervisor.py`. It imports the fixed `resource_supervisor.py` identity functions from that directory by absolute project-derived path, requiring SHA-256 `9589577c7f916f3b759fe8508e8cc8304820e810de56ad767264f83a2e72b1d6`. The imported file is unchanged. It retains the exited-parent zombie-row handling, current start-identity and group-membership checks, one-second observation, and fail-closed cleanup. No run or `resource-control` directory was created in preparation.

The supervisor takes `--manifest /absolute/path/to/manifest.json`. The manifest must contain: `execution_authorized=true`; `source_commit` (actual dispatch HEAD); `budget` exactly `{workers:1, P3:1, P2_conditional:1, per_phase_seconds:90, total_seconds:600, retries:0}`; `output` exactly this directory's absolute `run`; `candidate_directory`; `plan_sha256`; `control_file`, `control_sha256`; `admission_file`, `admission_sha256`; `probe_sha256`, `guard_sha256`, `helper_sha256`, `supervisor_sha256`; `inputs` with exact path-to-SHA mapping for the full `src/q3` tree, official code tree, `case_005.json`, `config.txt`, and `uv.lock`; and `command` as the exact Python argv below. The real admission file must exist with matching SHA. Absent authorization or any mismatch stops before `Popen`. A pre-existing `run` or `resource-control` also refuses dispatch. The new admission and manifest are to be supplied and frozen by root/team scheduler; this task does not create authorization.

```text
[sys.executable, -B, -m, src.q3.layered_query_flow_probe,
 CANDIDATE_DIRECTORY, OUTPUT_DIRECTORY,
 --source, SOURCE_COMMIT, --plan-sha256, PLAN_SHA256,
 --admission-file, ADMISSION_FILE, --admission-sha256, ADMISSION_SHA256,
 --control, CONTROL_FILE, --control-sha256, CONTROL_SHA256]
```

The child starts one new session/process group. The probe's P3 and conditional P2 workers inherit it; the supervisor rejects any observed worker in another group. The supervisor watches pressure level 1, other scorer count 0, disk free at least 10 GiB; while running it stops its verified group for RSS over 2 GiB or swap used growth over 256 MiB from the T0 sample. Physical free and swap free are recorded without a 6 GiB hard gate. It records initial and final observations plus an external wall from before T0 resource observation through the final sample. One-second polling does not guarantee a hard peak bound, and this resource proposal still needs a new scheduler admission.

Pure mock: `python3 -B results/a/q3-nikolastarx/layered-one-shot-20260925/test_supervisor_mock.py` passed three cases: resource thresholds and low-free observation, exited-parent/verified-group/reused-or-unknown identity handling, and rejection of an unapproved manifest with zero `Popen` calls. All signals were mocks. No real child, solver, official evaluator, Task, Step or constructor was called. The full `main()` lifecycle, newly supplied manifest, live macOS process races, actual R9 outputs, and momentary resource peaks remain unverified. Neither `layered_supervisor.py` nor this note authorizes the R9 batch.
