# P2 maximal-component cut scope under three orders

From the repository root, run `python3 -B scripts/q2_multiorder_cut_scope_scan.py`. The script reads the 100 official graph JSON files inside `data/raw/a/official-cases.zip` without extraction and writes `summary.json`; it calls no evaluator. Script SHA-256: `4317bed86b06667891aa005310384781117c8a965b204fd5a0d9ef140cfb6e81`. Input ZIP SHA-256: `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528`.

For each graph, select the largest weak component of the contracted compute DAG by eligible operation count, then compute cycles. Analyze only the 31 graphs where it has at least 1000 operations. A prefix qualifies when it and its suffix each have at least 10% of that component's `max(1, cycles)` work. Each crossing physical tensor ID counts once, regardless of repeated edges or consumers. The byte denominator is the sum of distinct tensor sizes with both an eligible producer and consumer in the component; it excludes external-only input and terminal-only output tensors. A ≤1% crossing-byte result is an independent filter and can still involve many crossing tensors.

The three fixed topological orders are the existing `DAGIndex` order, a ready queue ordered by descending critical tail, and the same queue ordered by ascending critical tail, with operation ID ties. Per-case minima and qualifying prefix counts are in `summary.json`.

| Order | ≤1 crossing tensor | ≤4 crossing tensors | Crossing bytes ≤1% |
| --- | ---: | ---: | ---: |
| Existing | 4/31 | 10/31 | 28/31 |
| Longest tail first | 3/31 | 4/31 | 27/31 |
| Shortest tail first | 3/31 | 6/31 | 11/31 |
| Any of three | 4/31 | 13/31 | 31/31 |

The four single-tensor cases are 016, 024, 051, and 072. The ≤4-tensor union includes 002, 016, 024, 031, 035, 048, 051, 062, 063, 068, 072, 077, and 088. This bounded scan is evidence about these three prefix orders only. It does not establish an optimal graph cut, legal capacity, early delivery, or official Makespan improvement.
