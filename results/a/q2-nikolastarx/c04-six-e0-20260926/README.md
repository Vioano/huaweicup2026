# C04 final pilot: six valid official runs, six Makespan regressions

The frozen width-32 C04 constructor did not pass the predeclared promotion rule. All six candidates are officially valid, have zero spill, and reproduce the static COPY-byte ledger, but all have worse Makespan than the same-cell completed c665 control. **C04 is not promoted to full500.** Under the user's final-round stop rule, no further Pro request or optimization trial follows; the paper's main P2 algorithm remains the completed fixed c665 full500.

| Case / cores | c665 control cycles | C04 cycles | Makespan increase |
|---|---:|---:|---:|
| 005 / 5 | 33,515 | 38,209 | 14.01% |
| 016 / 5 | 2,091,375 | 2,399,125 | 14.72% |
| 019 / 5 | 16,247 | 28,514 | 75.50% |
| 025 / 5 | 942,938 | 975,658 | 3.47% |
| 039 / 5 | 449,653 | 494,942 | 10.07% |
| 075 / 5 | 343,930 | 452,120 | 31.46% |

019, 039 and 075 reduce total COPY bytes compared with their controls yet increase Makespan. This is a concrete official counterexample to treating a byte improvement plus a zero-spill certificate as a sufficient Makespan improvement test. It is not a proof that all port-packet designs or all untested graphs fail.

## Identity and resource observations

- Frozen source/runner/preparation commit: `1284085f83127c211651a1148889688c7ee8f701`.
- Preparation manifest SHA256: `93935755943d207d4200a1d8734b5198a44b8b280a457968c53ab2344d98016b`.
- Runner SHA256: `dac86f790dcf2464b8c1fedacfac4f9f6bff0303f7ec0926891800b20507315d`.
- Archived coordinator gate SHA256: `6a267bcb68d3eb027f0c24237838a14b3dff7cf0d10b576441dd34473397fd16`.
- Actual calls: six independent E0, zero E1/E2/retry; all exit code 0, no timeout, no surviving child. The coordinator independently reread all six original results, hashes, process receipts, trace/log presence and COPY/zero-spill agreement.
- Ledger dispatch window: `2026-09-25T20:23:54.673461Z` to `20:24:03.588371Z`. Whole runner wall including preflight: **9.992930 s**. The ledger starts after preflight, explaining the different interval.
- Maximum observed observer-inclusive process-tree RSS: **391.42 MiB**. One P2 worker ran alongside the unchanged P3 worker on the shared Mac. These wall times establish a successful bounded parallel run, not a dedicated-machine speed comparison.

## Artifacts and timing boundary

`report.json` records every coordinate, movement fields, time, decision and compressed artifact hash. `ledger.json` is a personal-path-redacted derivative with its original hash; original local receipts remain unchanged. Each coordinate contains deterministic gzip archives of the complete unmodified official result and trace, official log, stdout/stderr and process receipt. Redacted receipts/stdout are explicitly flagged in the manifest, with both original and derivative hashes. The frozen plans, graph identities, code/config identities and old E0 controls are referenced by the [preparation manifest](../c04-six-pilot-preparation-20260926/manifest.json). Original graph bytes remain in the frozen official ZIP rather than being duplicated here.

These are offline constructed plans evaluated once for mechanism falsification. Construction's earlier in-process time is not cold solver time; this batch is not a complete online algorithm benchmark and must not be presented as a new full500 score. The targeted six-cell set was selected after static screening and is not a blind holdout.

The retained paper main result is [c665 full500](../hypergap-full500-audit-20260925/RESULTS.md): one fixed algorithm, 500/500 independent E0, K1–5 arithmetic means 1.206139 / 2.316727 / 3.235566 / 3.971149 / 4.549757.
