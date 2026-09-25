# Static inventory freeze

One Python process, <=30 s; no imports from `src/q3`, no plan construction or official evaluator. First error stops with zero retries. Source Forest root: `/Users/nikolastar/.codex/worktrees/p3-forest500-s59ee-20260925/huaweicup2026` (read only). Output is `inventory.json` plus captured stdout.

SHA-256 before execution:

| Item | SHA-256 |
| --- | --- |
| `inventory.py` | `6d02bc27eed46f6fe035c4f9084567a3b8bc3978ea734fb444cdda89e57ba1dd` |
| `forest-current-headroom-20260925/cells-snapshot.json` | `cf6021229b57458db772920faf8cdf995c0dc35a381d8f043254aa6a99f341cb` |
| `data/raw/a/official/data/case_065.json` | `23342b7c3e75f58cec3d0bdaff89bf8d6f18de4930d35ec2ceade91670f0a400` |
| Forest 065/K5 plan | `f28ed7c83d9c9b838ad6f905b7869520fd481af21a5e1972b4a4d4e75176f7be` |
| Existing `path-recovery/readback.json` (read separately for interpretation) | `074a09098174e28c37359c2891c0b614522ffbefc4e8f10b97f5241f105c5e76` |
| Read-only `src/q3/construct.py` (assignment rule) | `942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73` |

The process reconstructs the original op graph, contracts COPY nodes, forms the same weak components as `construct.Index`, and reads ownership from the saved plan. It counts original eligible PIPE_M/V cycles and tensors shared with other components. These are structural metrics, not E0 timings or a candidate score.

After execution: `inventory.py` SHA remained `6d02bc27eed46f6fe035c4f9084567a3b8bc3978ea734fb444cdda89e57ba1dd`; `inventory.json` SHA is `b380311c98265eb6a6d398dd6662b66ab3eb68d39d8237c243e9facf893fb37d`; captured `stdout.json` SHA is `0ffa8987561c1b511eabac42cfdddfdafb7476e9e9f301a8d3e9e266cdb16567`.
