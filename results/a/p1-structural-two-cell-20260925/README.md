# P1 structural refinement transfers to 016 and 024

The fixed unified structural solver `3a1b82b71ca1ff6689eb8e72f17d26c48b52073c` completed both targeted K5 cells with official E0 confirmation. It automatically selected `intact-root-heavy-fused` on each input. These are two new official cells, not a new full-500 benchmark or a case-ID selection table.

| Case, K5 | Unified-v4 Makespan | New Makespan | Reduction | Cold solver wall | External E0 wall |
| --- | ---: | ---: | ---: | ---: | ---: |
| 016 | 3,223,183 | 2,941,234 | 8.7475% | 42.6448 s | 31.8929 s |
| 024 | 1,067,515 | 974,062 | 8.7543% | 11.6741 s | 6.0455 s |

Makespan is simulated cycles. Solver wall is the fresh solver process through exit and output publication, including its online E1 calls. OS cache state was not measured. These walls are from Colab CPU; the prior Mac walls cannot establish a solver speedup or slowdown. Whole-window controller wall was 139.8393 s, remote wrapper wall 106.0816 s; neither replaces solver wall.

Extra DDR fell by 8,528 bytes on 016 and 2,816 bytes on 024, to 119,547,424 and 39,324,832 bytes. Both have zero spill. Full raw movement fields and comparison provenance are in `comparison.json` and the official result originals.

## Mechanism and prediction

The constructor preserves each branch and fuses reductions whose predecessors are local to a Task, while assigning more branch work to the root core. This trades load balance against Task release delays and boundary copies. Both choices and fallback are part of the fixed runtime algorithm. The experiment tests the joint construction; it does not isolate either change causally.

Before execution, `SCIENTIFIC_SCOPE.md` predicted 2,941,234 / 974,062 cycles from the saved 051 timeline. Both predictions matched exactly. The new official timelines have first-round completion 9,762 and every subsequent round increment 9,643: 304 increments in 016, 100 in 024. This supports transfer along repetition count in this family; it does not prove the same period after changing width, tensor sizes, arithmetic weights or reduction topology.

## Identity, execution and limitations

- Fixed runner/package: `c44f0558c11f2f45030c8d1e1ea0ae51d9629e7c`; `src/review/p1_structural_two_cell_once.py`.
- Artifact manifest SHA-256: `395f8e4e73c84f6ccc54a076ca50c0b4008e182d080ff84443d70c3ead0261c8`.
- Original downloaded archive: 1,421,280 bytes; SHA-256 `8c2015ef3d2721804f2e903ca369a917474cd9f453c7b212e6866c03ca37664d`; 33 payload files individually verified against its manifest.
- Actual calls: 2 solver, 8 online E1, 2 external E0, 0 E2, 0 retries; one worker. Each cell used 1 solver, 4 E1 and 1 E0. No further scoring was launched.
- Controller launched at 2026-09-25T10:56:32.375232Z. All solver/E0 children exited 0 with cleanup confirmed. Driver and remote adopted-child checks confirmed cleanup. The named VM stop returned 0, both controller and independent root fresh session queries returned empty, and the detached watchdog had exited.
- The preflight folder preserves preparation and zero-score regression evidence, including the independently found identity-acquisition failure and its repair. Preparation is distinct from this executed run.

The accepted same-algorithm full-500 K5 mean remains **4.025907473836023** for unified v4 `a0537aeb72dc702af86d67d3194587d581ac207c`. Replacing only these two cells arithmetically would add about 0.00459 to that mean; this is a prioritization diagnostic, not an observed unified mean. It does not justify declaring the user's requested substantial full-benchmark improvement complete or automatically launching another full batch.

Next research should preserve this demonstrated family improvement while identifying broader recoverable bottlenecks. The user-requested pause occurs after a significantly improved complete unified benchmark, publication and synchronization, not after this two-cell result.
