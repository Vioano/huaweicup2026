# Resource supervisor terminal-path candidate

Source copy: `query-flow-one-shot-20260925/resource_supervisor.py`, SHA-256 `651a8a9ee62253961abc656bfa50e01cdca4e17b5f799ad7d233826dcd438fa7`. This copy: SHA-256 `9589577c7f916f3b759fe8508e8cc8304820e810de56ad767264f83a2e72b1d6`.

Diff scope: check `waitid` before live-parent sampling and again after sampling, covering exit races; use a separate exited-parent finalizer that records exit code without asking libproc for the ended parent's identity. In this finalizer, only observed process groups with a currently matching leader and all matching member start identities may receive SIGKILL. An unobserved process carrying this run's unique output path, an unknown identity, or a reused PID fails closed with no signal. Existing pressure/free/conflict/600-second guards, one-second sampling, plan/source pins, and zero-retry budget remain. Swap remains an observation only, as in the copied R2 script.

Validation: `python3 -B test_terminal_mock.py` passed pure mocks for normal parent exit with unavailable identity, verified residual worker group, and reused/unknown identity refusal. See `terminal-mock-results.json` and `terminal-mock.stdout.txt`. No real child process, scorer, Task, Step, constructor, or official evaluator was started.

Limits: These mocks exercise terminal helper behavior, not the full `main()` lifecycle or macOS `ps`/libproc races. A process that escaped into a group never observed and does not carry the unique run path cannot be attributed after parent exit. Group membership can change between the last check and SIGKILL; the check is immediately before signalling but cannot make the OS operation atomic. This candidate is not authorized for scoring or an additional R2 run.

The copied interface and admission thresholds are unchanged. Any new window's resource policy and E0 budget require separate approval from the team scheduler; this terminal-path candidate supplies neither.
