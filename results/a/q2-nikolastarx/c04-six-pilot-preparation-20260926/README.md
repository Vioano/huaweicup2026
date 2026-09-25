# C04 six-cell official falsification — prepared, not executed

This freezes exactly one width-32 candidate for each of 005/016/019/025/039/075 at K5. Selection uses already available structural and static byte data: 005/016 are large connected graph controls; 019 has 31 components; 025 has 2,666 repeated seven-op components; 039 has 70 reduction trees; 075 is a connected graph with a large static COPY-byte decrease. A COPY-byte decrease does not predict Makespan. There is no case-specific solver rule in this pilot.

`manifest.json` pins every plan, original graph/config, constructor dependency (including the archived Pro kernel), the completed c665 baseline result and plan originals, and the evaluator source manifest. C665 controls are reused only as already audited fixed-plan E0 evidence; their solver time is not assigned to C04. `scripts/q2_c04_prepare_pilot.py` reconstructs and checks these candidates against the completed static scan without any scoring.

| Case | Eligible ops | Components | Largest component | c665 Makespan |
|---|---:|---:|---:|---:|
| 005 | 4,113 | 1 | 4,113 | 33,515 |
| 016 | 17,995 | 1 | 17,995 | 2,091,375 |
| 019 | 647 | 31 | 170 | 16,247 |
| 025 | 18,662 | 2,666 | 7 | 942,938 |
| 039 | 5,250 | 70 | 75 | 449,653 |
| 075 | 7,410 | 1 | 7,410 | 343,930 |

The runner is `scripts/q2_c04_frozen_pilot.py`. Preflight takes `--manifest results/a/q2-nikolastarx/c04-six-pilot-preparation-20260926/manifest.json --commit <fixed SHA> --preflight-only` and performs zero scoring. Actual execution requires the coordinator's matching, unexpired `admitted` gate and `--output output/c04-six-e0-run-20260926`. The proposed limits are six E0 processes, one worker, 30 seconds per process, 240 seconds for the batch including preflight, 1 GiB observer-inclusive RSS, zero E1/E2/retries. Source/input/gate mismatch fails before scoring. Failure, timeout, surviving child or official/static byte/zero-spill mismatch stops the remaining calls. A quality regression is recorded and does not abort the other fixed cells.

Example after a separate coordinator admission:

```sh
uv run --locked python -B scripts/q2_c04_frozen_pilot.py \
  --manifest results/a/q2-nikolastarx/c04-six-pilot-preparation-20260926/manifest.json \
  --commit <fixed SHA> --gate <coordinator gate> \
  --output output/c04-six-e0-run-20260926
```

There is no scoring admission in this directory. No official C04 result exists at preparation time. Offline construction times in the manifest exclude cold startup and are not full-solver timing.

Promotion requires valid E0 and matching zero-spill/COPY accounting, plus Makespan improvements in at least two of these structural classes: connected DAGs (005/016/075), medium fragmented graph (019), repeated tiny components (025), reduction forest (039). Otherwise seal the negative result, stop Pro/optimization as requested, and use the best completed same-algorithm full500 (c665) for the paper. If passed, freeze an input-driven incumbent+C04 online selector with at most one additional candidate; all selection cost is included in cold solver time. A new full500 still requires its own frozen runner/manifest and resource admission.
