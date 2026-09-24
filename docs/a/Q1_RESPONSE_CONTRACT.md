# P1 response contract prototype

Owner: `nikolastarx/s-6607cb2735304751b36662035723372b`.
Base algorithm: `a0537aeb72dc702af86d67d3194587d581ac207c`.
This prototype is not wired into the unified solver and has no new official
case score. It does not change the completed v4 full500 result.

## Purpose and current scope

The observed DDR-load-only selection failure means that extra search time can
select worse plans if the response model omits FIFO blocking and shared-DDR
feedback. Pro R2 proposes a synchronous packet DP whose transition costs retain
those effects. Before using such costs, this change replaces the author's
transcribed compiler with the actual frozen official Task compilation path.

- `src/q1/response_compile.py` calls the original `_build_scene_a_tasks`, which
  performs Step1, Step2 and Step3. It converts the actual FIFO orders and
  predecessor graph to per-Pipe completed-prefix requirements, using official
  operation duration and DDR-participation helpers. These are static compiler
  calls, not executions of `evaluate_scene_a` or E1/E2.
- `src/q1/response_oracle.py` implements the declared exact-rational DDR model
  with integer operation retirement, all four FIFO pipes, private Task gates,
  and at most one operation per Pipe. Both MTE2 and MTE3 can be in flight.
- The quotient folds only equal compiled signatures at a common empty-state
  release. It multiplies each already-rounded COPY service by participating
  core count. It does not round aggregate tensor bytes. At the first mismatch
  it simulates the entire remaining tail explicitly; it adds no new barrier.

Compiler acceptance is deliberately restricted to the Pro transition class:
single-producer managed tensors, aggregate Task footprint fitting each private
memory, and no spill/MEM dependency or cross-core Task dependency. Unsupported
plans raise an error rather than receiving an optimistic score. These guards
do not imply that unsupported plans are illegal or inferior under E0. Later
relaxation must account for the compiled memory dependencies explicitly.

Same-core tensor cuts **are** supported. During review, the first adapter
mistook official `cross_task_traffic` for cross-core traffic. The official count
includes same-core Task boundaries. Ownership-based dependency checking replaces
that incorrect rejection; a 61-byte same-core tensor cut is the regression
witness. This matters directly for the proposed pending-return DP.

## Validation completed

Command from the repository root:

```sh
python3 -m unittest tests.q1.test_response_compile tests.q1.test_response_oracle -v
```

Ten tests pass on macOS in this checkout. Six static compilation tests cover
seven tiny hand-built graphs, actual boundary COPY rounding, prefix order,
same-core tensor cuts, and explicit rejection of unsupported structures.
Four mathematical tests cover simultaneous input/output COPYs, two synchronized
rounds, shared fractional service, unequal tails and invalid dependency cycles.
The three-core two-round analytical witness is 22 cycles (two 9-cycle responses
and one 4-cycle gate). These are synthetic contracts, not official case results.

The implementation subagent used Sol/medium with a 7000-token soft estimate;
actual model usage was unavailable and no hard token cap was claimed. Root
review corrected the same-core cut bug and strengthened imported-module and
one-slot checks. Local checks made zero solver/E0/E1/E2 calls; model-unit calls
are separate from scoring. No new packages, services or cloud jobs were used.

## Remaining adoption gate

The official event loop uses binary64 residual service and EPS=1e-9, while this
oracle uses Fraction arithmetic. Their equality is not yet established.
Compiler fidelity and rational-model unit tests cannot establish that equality.
Before treating costs as an official oracle, a fixed finite differential batch
must compare both whole-plan Makespan and every operation's start/end times,
including simultaneous DDR requests, non-divisible work, FIFO depth ties,
multiple core counts and the first divergent round.

The candidate-generation alternative remains available: use rational response
only to propose a legal DP plan, then score it with the existing validated E1
inside the complete solver budget and retain the incumbent on a worse result.
That would be heuristic candidate generation, not a claim of exact E0 DP
optimality. No DP integration or extra scoring batch is released by this note.

Reference: complete Pro R2 and qualified reviews at fixed commit
`d6e640a337001e333108f592e6876ac6bd0a2561`, stable directory
`AI chats/P1多Pipe链构造证明/`. The archive's model experiments and conditional
335819 lower bound for084 remain separate from local official performance.
