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

## Pending-return candidate constructor

`src/q1/packet_dp.py` now builds one candidate for private homogeneous
M–V+–M chains on 2–5 cores. It derives the packet size from graph footprint
and capacity, then optimizes pending-return states. `full` uses `0..Q`,
`three` uses `{0, Q-1, Q}`, and default `auto` chooses full only if its
precomputed compilation-count upper bound fits the declared budget. It selects
the smaller state set before compilation if necessary, without rerunning a
failed full search. A
return-only Task can drain a pending state without consuming another packet.
The objective is lexicographic rational-model cycles, COPY bytes, and Task
groups. The final incomplete packet is simulated explicitly.

Each transition is compiled through the frozen official compiler on its
projected original nodes, preserving tensor input/output boundaries. After
reconstruction, the complete original graph and two-key plan are recompiled:
every selected Task signature, total COPY bytes and full rational response
must match the profiled transition path. Any mismatch rejects the candidate.
There is no official scoring or integration with the unified solver yet.

For R complete packets, S pending states and K cores, at most S squared normal
transitions and S-1 drain transitions are considered per layer, each compiling
at most K Tasks. DP uses O(R times S squared) transition work; actual cost
additionally includes official static compilation and response simulation,
and the final whole-plan compilation. The default 10000-Task compilation
ceiling is checked before compilation using a bound including the tail and
final plan, then checked against actual calls. This is a count limit, not a
wall-clock or per-Task size limit; deployment also needs an outer process
timeout. Current experiments use a 120-second constructor child limit.
This optimizes only this accepted packet template with fixed remainder
treatment under the rational model. It is not an optimum over all P1 plans.

An experimental `--profile-cache ordered-graph` option reuses projected Task
profiles after normalizing the joint original op/tensor ID order, preserving
list order, all other attributes and the compute-member set. The input graph
is never renumbered. Default is `none`: equivalence for every unselected
transition has not been proved. With caching, the algorithm is a candidate
proposer and does not claim even template optimality. Its complete final plan
still undergoes independent actual compilation and signature/DDR/response
checks; cache-derived labels are never treated as final operation trace IDs.

Three new tests cover a drain that beats every direct continuation, a 12-chain
two-core multi-round construction and a seven-chain three-core remainder.
The latter two execute small synthetic constructors; they are not official
case performance measurements.

## Frozen differential probe and finite E0 acceptance

`src/q1_benchmarks/response_contract_probe.py` defines exactly three micrographs:
two symmetric two-round plans at K=2 and K=3, and a K=3 plan whose second
round diverges. The 121-byte input and 61-byte output force non-integral
byte/bandwidth ratios and overlapping MTE2/MTE3 activity.

Preparation freezes input, plan, model output, official files/config, probe,
compiler, oracle and the process-cleanup helper by SHA-256. The separate `run`
command permits at most three sequential unmodified E0 CLI calls, 10 seconds
per child, no retry, first error/mismatch stop. It compares full Makespan,
every operation's start/end, all data-movement counters and Task-cut bytes.
The 90-second budget controls new-call admission; cleanup and final evidence
writing are recorded, and it is explicitly not a hard parent-process watchdog.

Root review added missing DDR comparisons, froze the process helper, and
clarified that timing boundary. The current prepared input is
`output/p1-response-contract-probe/prepared-20260925-v4`; earlier preparations
predate those corrections or runtime receipt metadata and must not be executed.
The original preparation made no E0/E1/E2 calls. Subsequently s59 executed
exactly three unmodified E0 calls under Python 3.12.13, with zero solver/E1/E2
calls and no retries. Total probe wall time was 0.243 seconds. Symmetric K2,
symmetric K3, and divergent K3 returned 128, 138 and 138 cycles respectively.
All 64 operation start/end pairs, whole-plan/quotient Makespan, data-movement
counters and Task-cut bytes matched. Root independently rehashed every saved
artifact and recomputed these comparisons without rerunning E0.

Frozen original inputs, source snapshots and official outputs:
[`0eff53c` probe archive](https://github.com/huaweibei123/huaweicup2026/tree/0eff53caa7a95d87a578fa82fe858b66f6d31cef/output/p1-response-contract-probe).
This is finite synthetic evidence, not proof of general binary64 equivalence
and not a new official-case result or board batch.

Current validation command:

```sh
python3 -m unittest tests.q1.test_packet_dp tests.q1.test_response_contract_inputs tests.q1.test_response_compile tests.q1.test_response_oracle -v
```

Result: 16 tests passed on Python 3.12.13/macOS 27 arm64 after adding full-state
budget selection tests. The earlier 15-test run used Python 3.14.5. Coverage includes
the two synthetic DP constructions, three static response fixtures, and a
regression proving unchanged timing cannot conceal a DDR-byte mismatch.

Reference: complete Pro R2 and qualified reviews at fixed commit
`d6e640a337001e333108f592e6876ac6bd0a2561`, stable directory
`AI chats/P1多Pipe链构造证明/`. The archive's model experiments and conditional
335819 lower bound for084 remain separate from local official performance.

## Experimental guarded unified entry

`python -m src.q1.response_refine INPUT --cores K --output PLAN --diagnostics DIAG`
is a separate experimental entry around the unchanged v4 `unified.solve`.
Only an actually selected `capacity-return` winner with its own successful
online score and matching plan SHA triggers one packet-DP child. The child
uses automatic state-budget selection and ordered-graph proposal caching.
A byte-identical plan needs no new score; a distinct legal plan receives at
most one E1 call. Only a strict `(Makespan, scheduled COPY bytes)` improvement
replaces the baseline. Child, validation or scoring failure retains the baseline.
No case identifier, saved plan or score table participates in this policy.

The 120-second child timeout is a termination trigger, not a hard total wall
limit; process cleanup and temporary-file work remain charged. CLI completion
reports through both output fsyncs; an external runner must also include process
startup and shutdown. The baseline and refinement call ledgers are separate.
If a score attempt throws after possible dispatch, the refinement reports its
actual count as unknown in `[0,1]`, rather than falsely reporting zero.

Four injected controller tests and one subsequent exception-accounting test
passed; these use fake expensive boundaries and do not run a real solver or
evaluator. Read-only review checked baseline hash binding, failure fallback,
single additional E1 scope and process cleanup. Real CLI operation, broader
graph coverage and non-macOS behavior still require validation. This entry
does not replace the existing production solver or inherit its full500 score.
