# P1 cross-round fusion: a necessary structural constraint

This note concerns an executable Task partition of the retained compute DAG.
It does not predict official FIFO, memory allocation or DDR timing, and is not
a global P1 optimum certificate. The motivating intact fork/join recognizer is
`src/q1/intact_frontier.py` at `9293aad78dde0dc170d05bc2c4142db634d46b4d`.

## Path closure of an executable Task

Let `p(v)` be the Task containing compute operation `v`. Contract each Task to
one vertex and retain every dependency between distinct Tasks. If this quotient
is acyclic, every directed path with both endpoints in one Task stays entirely
in that Task. Otherwise the path leaves that Task and subsequently returns;
after contraction it is a nonempty closed directed walk, which contains a cycle.

This is necessary, not sufficient. For example, original edges `a1 -> b1` and
`b2 -> a2`, with no other edges, give two individually path-closed Tasks
`A={a1,a2}` and `B={b1,b2}` but quotient edges `A -> B -> A`. An implementation
must still validate the full Task DAG augmented with per-core order edges.

## Consequence for repeated global fork/join rounds

Suppose round `t+1` forks from reduction root `r_t` and every branch rejoins at
`r_(t+1)`. Every operation of that round lies on a path between those roots.
Any executable Task containing both roots must therefore contain every compute
operation of that intervening round. Under P1, that round is then assigned to
one Task on one core: its operations cannot be distributed across cores.

Likewise, if a Task contains operations in rounds `t` and `t+2`, the path between
them passes through both intervening roots. Path closure places both roots in
the Task, and then places the whole middle round there. Therefore a partition
that keeps every round distributed over more than one Task cannot reuse one
Task across three rounds. This conclusion allows two adjacent rounds to overlap
inside a Task; it does not rule that construction out.

The possible next mechanism is consequently **two-round partial fusion**: a
Task may contain selected late branch work, its reduction-path closure and
selected work in the next round. This can retain some Task-local inputs, but
the other Tasks in the same next round forked from that root wait until this
fused Task has completed. This is not a claim about unrelated branches of a
more general DAG.
One must count the saved input copies and this added release delay together.
Combining an entire sequence of rounds to retain every input instead collapses
the intervening rounds onto one core and sacrifices their parallel execution.

## What remains open

- The closure argument does not give a tight minimum number of external-input
  copies; that requires the exact tensor incidences and Task compiler rules.
- A locally closed proposed fusion can still create a quotient or core-order
  cycle. Full derived-plan validation remains required.
- Neither lower DDR traffic nor fewer Tasks guarantees lower official Makespan.
  The existing 044/K3 full-core local-window probe is a separate negative
  example: balancing components increased Makespan from 64,624 to 68,109 and
  scheduled COPY bytes from 2,026,944 to 2,957,344, without spill.
- Before an implementation or another scoring window, a useful two-round
  candidate needs an explicit closure rule, saved-byte accounting and release
  dependency analysis. No such candidate has been measured in this note.

The scope is a proved necessary restriction on candidate construction, not a
reason to discard all cross-round fusion or to declare the current solver
optimal.
