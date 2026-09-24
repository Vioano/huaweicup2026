# P1 pending-return DP: static candidate evidence

This is **not an official performance result** and is not a benchmark-board feed.
Three constructors read the same official 084 graph on five cores. No E0/E1/E2
was executed. Input bytes are read from the frozen archive; the 5 MB original
is not duplicated here. Summary and manifest preserve hashes and provenance.

| Plan | Rational model cycles | Extra DDR bytes | Constructor wall seconds |
|---|---:|---:|---:|
| Saved v4 incumbent | 399121 | 9925632 | See original run |
| Three pending states | 397542 | 8939520 | 7.0759 |
| All six pending states | 397542 | 8939520 | 21.0724 |
| All six states, proposal cache | 397542 | 8939520 | 3.6181 |

The incumbent's static model agrees with its already-saved E0 values; this
is not a fresh E0 rerun. All three candidates have exactly the same plan bytes
(SHA-256 `5203ed797935cbf3777586247fa82191518485da839a6d680b150efb6ed5e3f6`).
The candidate model improvement is 1579 cycles, about 0.40%, with 986112 fewer
extra DDR bytes. Subsequent separate E0 acceptance is archived at
[084/k5 official result](../p1-response-dp-e0-20260925/084-k5/README.md):
Makespan 397542, extra DDR 8939520 and spill 0, matching these predictions.
The static constructions themselves made no scoring calls. Fraction-model/official-binary64 equality remains unproven generally.

The graph has 1077 private homogeneous chains. Capacity yields five chains per
full packet per core, 43 full synchronous packets, then two one-chain tails.
The selected transitions predominantly alternate pending counts 5 and 4,
with a final drain; 222 Tasks are emitted. Full-state profiling raises static
Task compilations from 2559 to 8889 and unique rational responses from 11 to 41,
but does not improve this plan. This excludes omitted pending counts as the
cause of this specific fixed-packet model gap, not other P1 plan families.

The third constructor adds `--profile-cache ordered-graph` at source
`59aee1fa1b5df8795de158dcc96ea160663efbe2`. Static Task compilations fall to 264
while the whole original graph and selected plan are still independently
recompiled and checked. The normalized ordered-graph cache proposes candidate
costs; equivalence for all unselected edges is unproved, so this version makes
no template-optimality claim. It returns the identical plan on this graph;
its saved E0 result, once obtained, need not be recomputed for identical bytes.

Source commits are recorded separately in each receipt. To reproduce a
constructor at that commit, extract `data/case_084.json` from the frozen
`data/raw/a/official-cases.zip` into a new output directory and run:

```sh
python -B -m src.q1.packet_dp INPUT_JSON --cores 5 --output NEW_PLAN_JSON --diagnostics NEW_DIAGNOSTICS_JSON
```

The first source defaults to the three-state implementation; the second
source defaults to automatic full-state selection within a precomputed
10000-Task compile-count budget. Each actual local invocation used Python
3.12.13, one fresh child at nice +10, one worker, a 120-second child timeout
and no retry. All exited normally and were reaped. Timings include interpreter,
input, construction and output; they are observational under shared machine
load, not a controlled runtime comparison. Synthetic unit-test calls are
separate from the three real-case constructors recorded here.

Follow-up: the separately frozen three-micrograph differential probe passed
all 64 operation times, whole-plan responses and DDR counters in three E0
calls, archived at commit `0eff53caa7a95d87a578fa82fe858b66f6d31cef` under
`output/p1-response-contract-probe/`. This does not change the zero-E0 scope
of the three real-case constructions above. One subsequent independent E0 evaluation of
this unique 084 candidate passed; see the separate official-result archive. Changing packet size or relaxing
synchrony is a new hypothesis; no further sweep is authorized by this report.
