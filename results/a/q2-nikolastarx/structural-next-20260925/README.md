# Structural diagnosis after the active-core full batch

`inspect_six.py` reads fixed data `60afc38b327680fbda0ff10182e3e05a01edd72d` and the unchanged original graphs. It verifies graph, plan and old E0 result hashes and computes static structural/COPY quantities. It runs no solver, Step1–3, E0/E1/E2 or new benchmark. `summary.json` preserves the exact input references and definitions.

| Case | Largest compute component | Cores containing it | Maximum topological layer within it | Cross-core contracted edges in the full plan | Mandatory DDR work | Existing E0 Makespan |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 003 | 13,194 | 1 | 324 | 0 | 28,129 | 515,736 |
| 005 | 4,113 | 5 | 196 | 2,067 | 59,022 | 66,385 |
| 056 | 7,464 | 1 | 162 | 0 | 3,872 | 253,392 |
| 068 | 4,176 | 1 | 96 | 0 | 46,604 | 295,114 |
| 086 | 5,274 | 5 | 256 | 3,483 | 90,161 | 102,180 |
| 088 | 2,798 | 1 | 96 | 0 | 33,141 | 200,888 |

All times are cycles, not solver seconds. Layer width is measured by longest-path topological levels in the largest component. It does not certify feasible concurrent execution under tensor capacity or bandwidth. Contracted-edge count is not COPY count. Mandatory work omits spills and is the documented integer-service model quantity; proximity to Makespan is evidence of pressure, not a proof that all latency is attributable to DDR.

The selected plans show two failure modes worth investigating: coarse whole-component placement can strand internal parallelism, while fine per-operation placement can create extensive communication. A strict four-operation same-Pipe closed diamond `P -> {X,Y} -> J` occurs zero times in these six graphs under the script's checks. That does not rule out larger closed regions; it does rule out directly applying that smallest Pro model as a ready-made solution here.

The next prototype uses maximal non-branching compute chains as placement units, retaining internal order, real pipes and original tensor identities. This is an intermediate granularity to test, not a claimed improvement. Before scoring, validate exact operation coverage, acyclic contraction, no unintended merge across fork/join boundaries, and the actual mandatory COPY counts. Compare against the frozen baseline through bounded full-plan evaluation; do not add a lookup table for these six cases.

If chain packets have little coverage or worsen transfer/compute tradeoffs, stop that candidate and inspect larger single-entry/single-exit regions. A future Pro question should use the actual uncovered structure and boundary tensors; the current narrow theorem and absent public E2 prepared-graph API do not justify another general proof claim.
