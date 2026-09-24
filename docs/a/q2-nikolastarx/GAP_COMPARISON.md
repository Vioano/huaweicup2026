# Whole-plan baseline versus join/gap candidate

`python -m src.q2_nikolastarx.adaptive_gap_guarded` is an experimental solver
entrypoint using the existing E2 CLI arguments. It has a four-coordinate
official pilot, but no full500 measurement yet. It constructs the complete `adaptive_budget` plan, including
existing semantic repairs, and a separate join/gap plan. Both are built online
from the current graph and configuration. No case ID, historical result or
stored winner selects the output.

The candidate adapts Fang's `src/q2/feedback/gap_packet.py` at
`71616ac7c4c7fca56e37e2d3245dd13725316d82`. Placement and the persistent resource
calendar originate in the P3 work at `a37eb931a22fb7df7e0d00d193538ce5289ae045`.
Our copied calendar is byte-identical to Fang's file; source comments retain
attribution. The adaptation uses our existing `DAGIndex` and rejects unsupported
graphs instead of invoking Fang's capacity fallback.

## Construction and selection

The guard requires unique original physical tensor producers, no logical tensor
aliases, matching physical/direct and COPY-contracted dependency relations,
and the presence of a fork and a join. Maximal serial chains become placement
units. Ready chains use remaining compute critical-path priority. If a chain
will release a join, both placements are considered together (at most k² core
pairs); otherwise at most k cores are considered. Persistent per-pipe interval
calendars permit insertion into previously unused gaps. The exported singleton
priorities follow modeled start time and topological position, then undergo
the existing official structural derivation check.

The model does not simulate shared DDR contention, spill, or memory-credit
dependencies. Its modeled times are neither official Makespan nor certified
bounds. The graph/chain indexing, O(k²(n+e) log n) conservative placement cost,
validation and I/O all belong to end-to-end solver timing.

Unsupported or failed candidate construction and identical plans request no
scores. Otherwise the existing isolated E2 adapter scores each complete plan
once, at most two requests. It checks native execution and strict nonnegative
integer scores. A strict lexicographic (Makespan, additional DDR bytes)
improvement selects the candidate; a tie or unknown evidence retains the
baseline. No downstream repair changes the scored plan. This entrypoint uses
no mandatory-DDR rejection rule, so the abstract floating-point bound caveat
does not affect its selection. A faster plan may use more DDR; secondary
tie-breaking does not guarantee non-regression of both quantities.

Initialization, construction, scoring, automatic fallback if encountered,
communication, validation and output are included in the solver's wall time
and call ledger. The existing CLI wall option remains unchanged; its default
does not alter any separately frozen experiment budget. Correct selection
depends on correct evaluator results in the actual domain. The earlier six
E2 samples do not prove this new candidate's correctness or quality.

## Validation and motivation

Four candidate/calendar synthetic tests and eleven complete-plan/adapter tests
passed. `results/a/q2-nikolastarx/gap-port-20260925/check_reference.py` additionally
compared 20 seeded tensor DAGs at 1/2/5 cores: all 60 adapted plans equaled the
original guarded placement function's plans. The reference uses a field adapter
and a rejecting fallback stub; it does not certify Fang's full fallback route,
official feasibility, unknown graphs or performance. No E0/E1/E2 was called.

The fixed-table comparison in `results/a/q2-nikolastarx/fang-feedback-20260925/`
verified 700 coordinates and matching per-case baseline values. Our current
2794 version exceeds Fang's older tensor full500 means. His new gap version's
complete k2/k3 means, 2.200110358/2.939676254, exceed our 2.050483457/2.815665259.
His extra DDR totals are higher. The new gap table is only 200 cells and must
not be labeled full500. This is a saved-table comparison, not a fresh audit
of all his source/result identities or a cross-machine runtime comparison.

## Official pilot and quality versus time

The four-coordinate run fixes solver `923b25ecb0b9d6d0e2d3f149fccef431b5403f99`
and runner `39341726395734626cd5dd903753cb1537c0f9a9`. Evidence is in
`results/a/q2-nikolastarx/gap-solver-pilot-20260925/`. Eight public E2 requests
returned native records; all four selected complete plans matched independent
E0 on Makespan, five movement fields and cross-task traffic. There were no
fallbacks, retries or surviving monitored descendants.

| Case/core | Baseline to selected Makespan | Baseline to selected extra DDR (bytes) | Outer solver wall (s) |
| --- | ---: | ---: | ---: |
| 003/2 | 511949 to 248166 | 98304 to 5067158 | 5.058 |
| 005/3 | 80167 to 49426 | 3101386 to 2394028 | 1.738 |
| 056/5 | 253392 to 96280 | 0 to 4863236 | 3.837 |
| 008/5 | 52291 to 52291 | 0 to 0 | 0.927 |

008 constructed a candidate with Makespan 233682 and rejected it after scoring;
the anticipated zero-score structural rejection was not exercised. The two
online score requests consumed 58–69% of outer solver wall on these samples.
External final E0 is excluded from solver wall and reported separately. Two
of the three improvements increased extra DDR; the selector does not dominate
the baseline on every metric.

These are targeted cases, not a random sample or a controlled experiment in
which only the time budget changed. They support testing more informative
construction and limited online comparison, not merely raising a timeout or
claiming that minutes of search must improve quality. The separate six-chain
pilot improved five cases and regressed one; its results are not spliced into
this algorithm's batch. A fresh frozen all-case run is the next quality and
latency check. Until then, the complete algorithm score remains the 2794 batch.
