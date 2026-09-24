# P1 pending-return DP: static candidate evidence

This is **not an official performance result** and is not a benchmark-board feed.
Two constructors read the same official 084 graph on five cores. No E0/E1/E2
was executed. Input bytes are read from the frozen archive; the 5 MB original
is not duplicated here. Summary and manifest preserve hashes and provenance.

| Plan | Rational model cycles | Extra DDR bytes | Constructor wall seconds |
|---|---:|---:|---:|
| Saved v4 incumbent | 399121 | 9925632 | See original run |
| Three pending states | 397542 | 8939520 | 7.0759 |
| All six pending states | 397542 | 8939520 | 21.0724 |

The incumbent's static model agrees with its already-saved E0 values; this
is not a fresh E0 rerun. Both new candidates have exactly the same plan bytes
(SHA-256 `5203ed797935cbf3777586247fa82191518485da839a6d680b150efb6ed5e3f6`).
The candidate model improvement is 1579 cycles, about 0.40%, with 986112 fewer
extra DDR bytes. It needs external E0 acceptance before being called a new
score. Fraction-model/official-binary64 equality remains unproven generally.

The graph has 1077 private homogeneous chains. Capacity yields five chains per
full packet per core, 43 full synchronous packets, then two one-chain tails.
The selected transitions predominantly alternate pending counts 5 and 4,
with a final drain; 222 Tasks are emitted. Full-state profiling raises static
Task compilations from 2559 to 8889 and unique rational responses from 11 to 41,
but does not improve this plan. This excludes omitted pending counts as the
cause of this specific fixed-packet model gap, not other P1 plan families.

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
and no retry. Both exited normally and were reaped. Timings include interpreter,
input, construction and output; they are observational under shared machine
load, not a controlled runtime comparison. Synthetic unit-test calls are
separate from the two real-case constructors recorded here.

Next: first execute the already-frozen three-micrograph differential probe
after the shared scoring window clears. Then independently E0-score this one
unique candidate if that check passes. Changing packet size or relaxing
synchrony is a new hypothesis; no further sweep is authorized by this report.
