# R3 independent checks

The source answer is `AI chats/20260924-Pro-P3-归约森林切分/最终回答-r03-20260924T2001Z.txt`, assistant message `049fd8c9-24cd-466e-90b8-a3671f7f01be`. Author examples are synthetic, not official cases. No author program was executed.

`verify_certificates.py` independently reads the downloaded JSON. It checks unchanged original operations/ports/dependencies, exact coverage, per-input releases, cross-core delays, per-pipe FIFO, nonoverlapping timing witnesses and an independently rebuilt DAG's ASAP makespan. All six baseline/candidate pairs passed; two deliberately invalid witnesses (missing communication delay and later external release) were rejected. `summary.json` is the generated result. This verifies these certificates, not general optimality, memory/cache correctness or production complexity.

Reproduce from project root:

```sh
python3 results/a/q3-nikolastarx/pro-r03-independent-20260925/verify_certificates.py \
 'AI chats/20260924-Pro-P3-归约森林切分/附件/r03-049fd8c9-abstract_certificates.json' \
 /tmp/q3-r03-certificates-readback.json
```

AT.11's sufficient-condition proof is valid in its compute/port/FIFO model: frozen outside intervals, feasible inside intervals and exits no later than the current full witness give a feasible stitched witness. Implementation must compare with that current witness, not merely a potentially worse same-home trial; every graph output must be included. Frozen external intervals are restrictive and may miss beneficial joint rearrangements. None of this proves an official E0 upper bound.

AT.15/16 was checked against frozen P3 COPY creation/release and Step2 backing behavior. `src/q3/copy_bound.py` charges necessary OUT + release + fastest IN service only on identified original cross-core tensor/direct connections. Inputs do not acquire an invented OUT, duplicate constraints take max, and ambiguous COPY contractions/multiple producers fail closed. For custom bandwidth orderings, the read minimum uses max(DDR, Cache). Nine new small tests passed; the complete Q3 suite ran158 tests,157 passed and one explicitly gated E0 test skipped. Fake-evaluator tests made no real E0 calls.

`copy-bound-existing-results.json` checks six already scored plans from artifact commit `7d11e18600474a15c51b1e94603bc1f0684943bf`. All plan/result hashes were checked. The new bound was between the legacy bound and recorded official M in all six. It improves the two pipeline bounds from25412/70776 to25458/70941; neither is newly pruned. This is limited evidence, not a broad speedup claim. No new E0 was run, and the helper is not yet used by online solvers.
