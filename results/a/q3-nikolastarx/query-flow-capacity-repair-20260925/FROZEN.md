# Independent repair phase, frozen before execution

The previous `query-flow-capacity-certificate-20260925/` attempt and its budget remain unchanged. Its actual script failed before graph analysis at `certificate.py:86` because Python `configparser` does not parse the official space-delimited config format. This new phase replaces that call with the official `evaluation_validation.read_evaluation_config(path)['capacity']`, the same reader used by `query_flow._capacity_from_config`.

Current R8 source commit: `65d7355ee0856783ede81328915e8bd43227c842`. Target original inputs: `case_005.json`, `case_086.json`, one decomposition each; config: original `config.txt`, L1 524288 and UB 131072 bytes. Frozen SHA-256:

| Path | SHA-256 |
| --- | --- |
| `data/raw/a/official/code/evaluation_validation.py` | `103206b8c5c25e37de50cc3193de3989d7c1e01d4a11cc5f509dedd8f9be9a64` |
| `src/q3/query_flow.py` | `88aca80c6e5dac46e56a6894a165e40aab7e21ac68db66b6dac83539a1d2d2f0` |
| `src/q3/attention_rows.py` | `a4076188bda3037cdaa22686bf85d20051a3d8020e02d78d46db36adc5c10bb9` |
| `src/q3/construct.py` | `942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73` |
| `data/raw/a/official/data/config.txt` | `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9` |
| `data/raw/a/official/data/case_005.json` | `c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f` |
| `data/raw/a/official/data/case_086.json` | `ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a` |
| `certificate.py` (new) | `657711175bc3383063ecc7e77a48ce0aa8afa4bd705b378e46b1df62d24b4b68` |

Static review before execution: Python AST parses. `Index(graph)` validates and contracts compute dependencies; `_ports(index)` exposes original tensors, producer and consumer sets; `_recognize(index, ports)` and `_decompose(index, ports, rows)` are called exactly once per case and return `label, keys, rows`. Each P/A/O flow's tensor support is the distinct set of original tensors touched by its compute operations, with DDR charged to UB. Shared S support is omitted. The finite DP checks every nonempty subset of at most 12 flows: a subset is allowed only when both pooled tensor-union byte sums fit capacity. Fixed lowest-bit anchoring covers all flows exactly once and returns minimum group count plus one witness. The script calls no plan constructor, Task, Step, solver, pipe_bound, or evaluator; `read_evaluation_config` only parses and validates configuration. Importing `construct.Index` does not invoke `Index.build` or `query_flow.construct`.

Execution limit: one Python script process, one worker, 30-second total SIGALRM wall limit, 005 then 086, no retries. Stop on first error and retain stdout/stderr. If either case has more than 12 flows, stop before subset expansion. E0/E1/E2/Task/Step/solver/pipe_bound/construct calls: zero. Report source/input/config hashes, singleton bytes, feasible subset count, exact-cover minimum group count, 5-core feasibility, witness, process CPU and wall. This is only a necessary capacity condition for the **whole P/A/O flow support resident on one core** family. It is not a lower bound on all legal P3 schedules; asynchronous reuse and spill can bypass it.
