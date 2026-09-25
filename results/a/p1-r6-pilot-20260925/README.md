# R6 branch-aid pilot preparation

This is a single mechanism test, not a fixed unified algorithm benchmark. At preparation no test, current-input construction or E0 has run. All old evidence remains unchanged.

The fixed command, run from this worktree after coordinator admission, is:

```sh
../../.venv/bin/python -B src/review/p1_r6_pilot_once.py --graph output/p1-r6-pilot-inputs-20260925/case_085.json --reference-plan output/p1-r6-pilot-inputs-20260925/reference-plan.json --output-dir output/p1-r6-pilot-20260925/attempt-1 --expected-head <full commit containing prepared-manifest.json>
```

Inputs are byte copies from the previously archived R6 input ZIP, recorded by SHA in `prepared-manifest.json`. Old result provenance is fixed commit `9c5f87548cc7588465a638e032993969b5cac891`, `results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/cells/085/k5/`. The constructor cannot read the old result or use the old plan to choose a cut. The reference raw plan is read only after current-input heavy construction, solely to test exact byte identity for baseline evaluation reuse.

The supervisor runs at most five tiny structural tests, one real heavy baseline, one branch-aid candidate, and conditionally one official E0. No E1, E2, parameter retry, or expansion is allowed. Timeout, failed tests, missing candidate, raw baseline mismatch, RSS stop or unconfirmed process cleanup abort subsequent stages. RSS is sampled process-group memory, not a continuously enforced memory limit; peak may occur between samples. Identity uncertainty stops work and records residuals rather than signalling an unverified group. Root must inspect terminal status and residual processes before release.

The 180-second window includes process supervision and artifact collection, with stage limits 10/30/120 seconds and a cleanup reserve. Source imports and artifact writes count in the child process wall; the probe's internal time excludes imports and its final receipt write. Test/supervision wall and external E0 wall are separate from candidate-generation wall. This prototype is not integrated into the unified selector, so its wall cannot be labelled full unified solver timing.

Evidence before execution: AST parsing of the new scripts and tests passed. Runtime tests and supervisor failure-path execution remain unverified; actual results will be appended without overwriting this preparation record.

## Supervisor race correction before admission

Preparation revision 2 is `prepared-manifest-r2.json`; revision 1 remains preserved. The supervisor accepts an already-reaped direct Popen child only when its return code is zero and its expected process group is observed empty twice. Uncertain/live identity still fails closed. The first zero-scoring regression had a failure in the test injection: its delayed identity lookup still observed a zombie, so it did not enter the branch the test intended to cover. The behavior returned success with no residual, but the extra test assertion failed. After changing only the test injection, the second run passed all three checks (fast success, rc3 stop, SIGTERM timeout cleanup). Both raw attempts remain archived; all process groups were observed empty. Total: six tiny Python children, zero algorithm constructors, solver, E0, E1 or E2. These checks do not replace the five still-unexecuted branch-construction tests.
