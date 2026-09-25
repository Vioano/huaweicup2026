# Case 065/K5 component inventory

Frozen inputs and script hash: `FREEZE.md`. Actual one-shot command (exit 0; stdout preserved as `stdout.json`):

```sh
perl -e 'alarm 30; exec @ARGV' python3 results/a/q3-nikolastarx/case065-mechanism-readback-20260925/component-inventory/inventory.py /Users/nikolastar/.codex/worktrees/p3-forest500-s59ee-20260925/huaweicup2026 > results/a/q3-nikolastarx/case065-mechanism-readback-20260925/component-inventory/stdout.json
```

The saved plan has **42** weak compute components, with **6/9/7/10/10** on cores 0–4. Reconstructed original PIPE_M work is **6320/6172/3680/5904/6184** cycles; PIPE_V work is **3075/6622/6577/6642/6602**. This matches busy-cycle totals already stored in `../path-recovery/readback.json` for those two pipes, but the original-cycle accounting alone does not explain E0 waiting. `construct.Index.assignment()` places whole components by normalized per-pipe load; `affine_eighth` changes only the within-core word, not ownership. The saved E0 task ends remain 8710/11270/9443/10964/11064, with core 1 last. Current placement is thus much lighter on core 0's V pipe, while its M pipe is already substantial.

Three **alternative**, dependency-closed whole-component candidates for a move toward core 0 are:

| Component | Current core | First op | Ops | M cycles | V cycles | Shared raw tensors with other compute components |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 11 | 1 | 414 | 42 | 0 | 2634 | 0 |
| 9 | 3 | 244 | 41 | 0 | 2621 | 0 |
| 10 | 4 | 329 | 41 | 0 | 2621 | 0 |

The full original node lists are in `inventory.json`. Under the COPY-contracted compute graph used by `construct.Index`, each is a weak component and therefore has no compute dependency edge to another component. The script also found no tensor touched by one of these components and an eligible op in another. This makes them concrete structural candidates with no *observed original shared-tensor frontier*, but says nothing about newly generated COPY operations, cache placement, or feasibility of a changed schedule. Moving all three to core 0 would add 7876 V cycles there, so they are alternatives rather than a combined recommendation. Even one move cannot be claimed to reduce Makespan from this inventory.

A generalizable **hypothesis** is a guarded post-assignment rebalance: among whole V-only weak components, consider an underloaded target core only when the moved component has no external compute edge and a small measured shared-tensor frontier; choose by the resulting per-pipe load vector, then separately validate the fixed plan. The 065 inventory supplies eligible objects, not proof that this rule improves E0. A falsifier is that core 0's task end increases to at least the old Makespan, another late core takes over without net gain, or added DDR bytes outweigh the quality change. No plan, score, or official evaluator was run here.
