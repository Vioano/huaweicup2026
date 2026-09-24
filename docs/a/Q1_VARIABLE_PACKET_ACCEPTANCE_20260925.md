# Variable-width packet construction: local acceptance and next scope

The fixed production v4 result remains 100 graphs × 1–5 cores at source
`a0537aeb72dc702af86d67d3194587d581ac207c`, with five-core arithmetic mean
speedup **4.025907473836023**. The experiments below cover **084/k5 only**;
they do not replace that full-suite result.

## Measured construction and official quality

| Method | Makespan cycles | Extra DDR bytes | Spill bytes | Measured solver wall seconds |
| --- | ---: | ---: | ---: | ---: |
| Existing v4 plan | 399121 | 9925632 | 0 | See fixed full500 record |
| Fixed-width packet DP | 397542 | 8939520 | 0 | 3.618072417 cached standalone observation |
| Variable-width packet DP | 390425 | 9031680 | 0 | 1.975573250 standalone observation |
| Unified wrapper with variable refiner | 390425 | 9031680 | 0 | 8.799125709 |

The variable constructor source is `75bdb89c2f7299636967bfd27ee47aa3b1bd8083`;
the wrapper source is `a0b43164e3c46ce8d0c7af47cc16960b9cace4b2`.
Both produce plan SHA-256
`bd30e21f6fb8a2c12e149902e90173acad7af377d9d06babe20619d56c6b1796`.
That plan was evaluated once by the unchanged official E0 before the local
constructor run; both later plans match the actual E0 input byte for byte.
E0 took 1.635401250 seconds, separately from solver wall time.
The standalone construction used no online E1. The wrapper used four baseline
E1 calls plus one refinement E1 call, and reused the existing E0 evidence.

The first attempted E0 launch failed before creating a child due to a missing
runtime path. The corrected launch produced the sole E0 run. Preserve both
startup receipts; zero subsequent evaluator reruns does not mean zero startup
failures. Timings are shared-host observations, not a controlled speedup study.

The variable plan reduces Makespan by 2.17879% versus v4 and reduces extra DDR
by 894432 bytes. Against the fixed-width DP it reduces Makespan by 1.79025%
but increases extra DDR by 92160 bytes. It does not dominate that plan in all
metrics. The fixed-v4-baseline comparison contributes approximately 0.001399275
to a hypothetical 100-case five-core mean if all other outputs were unchanged;
that arithmetic is not a newly measured unified mean.

Public original-byte evidence and receipts:
[standalone and E0 package](../../results/a/p1-variable-packet-local-20260925/084-k5/README.md).
The original Pro source, conditional proofs, and independent arithmetic audit
are archived at source `29a7b37f83c76c14799ca85a30b8c92d477212c5`, under
`AI chats/P1多Pipe链构造证明/`. Original author reports remain historical records;
this document supplies subsequent local verification.

## What the certificate does and does not settle

The new dynamic program varies packet width as well as pending-return count.
It checks private identical ordered chain descriptors, preserves original IDs,
requires a conservative capacity certificate, and recompiles every selected
Task on the original graph. Candidate selection remains guarded by online E1
in the wrapper. The baseline is retained on unsupported structure or failure.

The independently checked 43884 Bellman inequalities certify the optimum of
the declared finite synchronous state graph **conditional on its response
cost table**. They do not certify the global P1 optimum, arbitrary asynchronous
Task arrangements, or general rational-model/binary64 event equivalence.
One matching official E0 verifies this selected plan, not every unselected edge.

Further improvement of this family requires a justified enlargement of legal
constructions or a better physical model, rather than repeated search of the
same certified state graph. The existing v4 capacity-return winner appears in
only four saved full500 cells, all 084 at cores 2–5. Those IDs are diagnostic
observations; runtime routing uses graph structure and the scored winner only.

## Next research decision

Retain this useful mechanism and finish its fixed release evidence. Before
another full500 run, review complementary structural candidates together.
Fang's H/J fork-join mechanisms have measured partial evidence, but their
24-round routing guard is a development-domain restriction, not a general
legality theorem. Width-dependent binning and reduction-tail predicates must
be reviewed before widening the domain; changing just one guard is insufficient.

The negative shared-input Stage L experiment is also informative: exact byte
and isolated DDR-service counts matched E0 while Makespan was substantially
worse than v4. Thus a next shared-input constructor must account for FIFO order,
contention and fill/drain timing; lowering the byte/service proxy alone is not
an adequate acceptance criterion. No additional experiment is authorized by
this note, and no global impossibility or final-optimality claim is made.
