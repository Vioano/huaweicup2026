# Query-flow capacity certificate, frozen before execution

Source commit: `65d7355ee0856783ede81328915e8bd43227c842` (current R8). Target inputs: original official `case_005.json` and `case_086.json`, once each. Config: original official `config.txt`, capacity L1=524288 and UB=131072 bytes. Source hash of `query_flow.py` is `88aca80c6e5dac46e56a6894a165e40aab7e21ac68db66b6dac83539a1d2d2f0`; `attention_rows.py` is `a4076188bda3037cdaa22686bf85d20051a3d8020e02d78d46db36adc5c10bb9`; `construct.py` is `942450f2751eb5b0cf4817d392acdd6e4316e751c48ea8e84b509d4ce1e97d73`. Config hash is `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`; input hashes are 005 `c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f` and 086 `ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a`. Official code tree listing hash: `fa951ed67d2a209a3d6afa1a143f03ed8fdf835b648f2ac3497f06f57d42b2dd`.

Run one Python script process, one worker, total 30 second wall alarm. No retries. First error stops and keeps stdout/stderr. If r>12, stop without expanding subsets. Zero Task, Step, solver, pipe_bound, official construct, E0/E1/E2 or any scoring calls. This is a read-only graph analysis, writing only this results directory.

For every flow, include tensor IDs touching any original P/A/O compute op, charging original DDR position to UB. Shared S operations are ignored. A group support is the union of its flow supports; a group exceeding either physical pool is disallowed. Exact cover DP with a fixed smallest-bit anchor finds the minimum number of allowed groups covering all flows. Report singleton support, number of feasible nonempty subsets, minimum cores, five-core feasibility, and process CPU/wall. This is a necessary condition only for the R8 family in which an entire grouped flow support remains resident on its core. It cannot exclude other P3 placements, asynchronous reuse, or spill.

After the script is completely written, record its SHA-256 below before running. Then execute once only.

Script SHA-256: `d41c168825cf69067667399684171abf5d980333107e1888416b607891a7200d`
