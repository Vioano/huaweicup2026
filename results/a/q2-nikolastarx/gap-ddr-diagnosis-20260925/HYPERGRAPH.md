# Exact original COPY bytes as a placement objective

This is a pre-Step2 statement about bytes, not an official Makespan bound.
Source: frozen `923b25ecb0b9d6d0e2d3f149fccef431b5403f99`,
`multicore_cut_evaluate_problem_2.py::_build_scene_b_tasks`. The domain here has
at most one eligible producer per physical tensor, nonnegative integer sizes,
and no logical aliases. A pin is an eligible original op ID, not a consumer
occurrence or a chain label.

For a tensor of size `s`, let `C` be its distinct consumer cores and `p` its
producer core when present. Original COPY transfer bytes are:

- Input with consumers and no eligible producer: `s * |C|`.
- Producer plus consumers: `2s * |C \ {p}|`.
- Official output condition: an additional `s`, even if cross-core COPY_OUT
  operations already exist for that tensor.
- Eligible direct op edges: `2 * max(0, int(data_size))` when cores differ.

For an internal tensor, use one hyperedge containing the producer and all
consumer op pins. Its connectivity `lambda` counts distinct pin cores, so
`|C \ {p}| = lambda - 1`. Its weight is `2s`. An external input edge has only
consumer pins, weight `s`, and contributes `s + s*(lambda-1)`. Eligible direct
op edges are two-pin hyperedges with weight twice their normalized size.
Official outputs contribute constant bytes in the unique-producer domain.
Thus the whole pre-Step2 byte count is a fixed boundary constant plus weighted
hyperedge connectivity. With multiple eligible producers this reduction is
not justified: the official source/target Cartesian pairs must be counted.

Move a nonempty same-core group `U` from core `a` to distinct core `b`. For an
incident hyperedge `t`, let `n_t(c)` count its original op pins on core `c`.
Then

```
delta(lambda_t) = [n_t(b) == 0] - [n_t(a) == |t intersect U|].
```

Proof: the move adds core `b` precisely if that core was absent, and removes
core `a` precisely if all its pins move. All other occupied cores are
unchanged. Summing weighted deltas over incident hyperedges gives the exact
original-byte change. When contracting a chain, retain how many original pins
of each edge lie in that chain; counting a multi-pin chain as one original pin
breaks the removal test. Boolean presence per contracted unit is an alternative
only when every maintained count uses those contracted units consistently.

Consequences for the next solver version:

1. Fixed core placement fixes these original COPY bytes; changing only FIFO
   priorities cannot recover them. Reordering may still change spill and M.
2. Parent-chain cut counts are an inexact communication proxy. Exact marginal
   byte cost is available through incident-edge counters without calling E2.
3. A byte-decreasing placement may serialize computation or change memory
   lifetimes. It has no automatic official M or zero-spill guarantee. A core
   load bound is a relaxation, not a schedule-feasibility certificate.
4. The measured 003/056 increases are diffuse. Group-level placement, rather
   than repairing a few largest tensors, is worth studying. This is a research
   priority, not a measured improvement from a new algorithm.

`hypergraph-check.json` records equality of category counts against the static
counter and zero-spill E0 scheduled bytes on eight archived old/new plans.
The independent finite-set identity check used 2,000 seeded synthetic moves
and 6,889 incident edges, with no mismatch. These checks support the formula
and implementation on their stated domain; they are not another scored batch.

The new Pro r04 question asks for a restricted, computable construction that
combines this exact cost with heterogeneous parallelism, or a counterexample
to a claimed joint guarantee. The frozen full500 algorithm remains unchanged
while that question is in flight.
