# P2 single-exit prefix scope scan (static)

Run from the repository root:

```sh
python3 -B scripts/q2_single_exit_scope_scan.py --output results/a/q2-nikolastarx/single-exit-scope-20260926/summary.json
```

The script reads `data/raw/a/official-cases.zip` without extraction and writes only `summary.json`. Input ZIP SHA-256: `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528`. Script SHA-256: `f2d306d61182497c42f45997a05a4df910d83d79fe2c87031858a5941574c928`. No E0, E1, E2, Colab, or solver run is involved.

For each of the 100 graphs, `DAGIndex` supplies the contracted compute DAG and deterministic topological order. The selected weak component has the most eligible operations, breaking ties by compute cycles and then first occurrence. A prefix is nontrivial when both it and its suffix have at least 10% of this component's `max(1, cycles)` compute work. A physical tensor crosses if at least one eligible producer lies in the prefix and at least one eligible consumer lies outside. Each tensor ID is counted once even with multiple edges or consumers. The byte denominator is the sum of sizes of distinct physical tensors incident to at least one eligible operation in the selected component, including external inputs and terminal outputs. The 1% byte threshold is therefore a loose screening statistic. `summary.json` records each graph's component size and work, minimum crossing tensor count and bytes over nontrivial prefixes, and qualifying prefix counts.

| Selected-component scope | Graphs | One tensor | Crossing bytes ≤1% | Both |
| --- | ---: | ---: | ---: | ---: |
| All graphs | 100 | 53 | 77 | 39 |
| At least 100 operations | 70 | 34 | 68 | 33 |
| At least 500 operations | 33 | 4 | 33 | 4 |
| At least 1000 operations | 31 | 4 | 31 | 4 |
| At least 5000 operations | 14 | 3 | 14 | 3 |

The four one-tensor graphs with at least 1000 operations in the largest component are 016, 024, 051, and 072. In the previously prioritized large-component examples 005, 069, 071, 086, 068, and 088, the minimum crossing tensor counts are respectively 7, 7, 7, 8, 4, and 4. Thus the exact one-tensor topological-prefix rule has limited coverage of large components. This scan checks topology and tensor incidence only; it does not test capacity, early delivery in an official schedule, or Makespan. The counts do not rule out other structural cuts or topological orders.
