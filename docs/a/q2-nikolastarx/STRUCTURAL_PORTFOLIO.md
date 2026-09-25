# P2 structural portfolio: mocked contract check

`adaptive_structural_portfolio.build` keeps the guarded hypergap route as its
incumbent. It constructs three alternatives: fixed-owner reverse retiming of
that incumbent, an independent reverse-gap plan, and latency hyperrefinement
of a gap plan. These choices probe different ownership, ordering, and latency
structures. A construction proxy does not select a winner; the injected
complete-plan oracle's `(Makespan, added DDR bytes)` tuple is compared
lexicographically, with strict improvement required.

The route allows at most six distinct complete-plan oracle starts, including
starts made by the incumbent builder. Equal plans are cached. The frozen
incumbent builder has a three-start cap, leaving room for the three alternatives
when its selected plan was among those scored. If the incumbent returns an
unscored plan, the portfolio scores it before comparing alternatives. The route skips
portfolio construction for one core or unknown incumbent score evidence. A
missing or invalid score during comparison returns the incumbent with unknown
evidence. Its reported solver wall time must include construction and all
online scores; any external final evaluation is separate.

`tests/test_q2_structural_portfolio.py` uses only injected mock builders and
an in-memory oracle. It covers a win by each structural candidate, Makespan
regression and DDR tie breaking, duplicate construction, the six-start cap,
one-core and unknown-evidence skips, invalid score fail-closed behavior, and
the CLI's limit. Run with
`python3 -m unittest tests.test_q2_structural_portfolio` from the repository
root. On 2026-09-26 this passed: 8 tests in 0.004 seconds. An initial
`python -m unittest ...` invocation could not start because `python` is absent
from this shell. No real solver or E0/E1/E2 call was made.

This check establishes route behavior under mocked plans and scores. It does
not establish legality, official Makespan, actual candidate diversity on the
100 graphs, end-to-end runtime, or a full fixed-algorithm P2 result.
