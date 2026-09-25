# 065/K5 static readback freeze

- Source checkout: `035b1452bd3c77261b2afc1ee2a9c341321d956c`; forest source commit recorded by snapshot: `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`.
- Input selection: `results/a/q3-nikolastarx/forest-current-headroom-20260925/cells-snapshot.json`, case 065, five cores, best record `159222569e194252ad2ec2d971a286d6e9381b2f0590200d09ad615ce52f1d12`.
- Read-only source root: the existing `p3-forest500-s59ee-20260925/huaweicup2026` worktree. Its manifest, plan, result, run, and receipt all exist and match the snapshot SHA-256. Local raw `data/raw/a/official/data/case_065.json` matches snapshot graph SHA-256 `23342b7c3e75f58cec3d0bdaff89bf8d6f18de4930d35ec2ceade91670f0a400`.
- Fixed observed metrics to interpret: E0 Makespan 11270 cycles, single-core baseline 53068, generic bound 5904 (loose and not asserted attainable); solver wall 0.471 s in snapshot. Quality and solver time are separate.
- Hypothesis only: some of the 5366-cycle bound gap may reflect serialized core/pipe work or dependency release. DDR/cache causality is not assumed.
- Budget: no Task/Step/E0/E1/E2, constructor, solver, VM, or online benchmark. At most one static analysis process with 30 s wall limit; first exception stops with zero retries. Only this audit directory is writable.
