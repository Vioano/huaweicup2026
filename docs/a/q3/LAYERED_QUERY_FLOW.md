# R9 layered query affinity: guarded local port

Source: ChatGPT 6 Pro response message ID `6ea4bc79-c48b-4b9a-9eac-90b1d4aad4a8`, archived attachment `AI chats/20260925-Pro-P3-多层查询亲和/附件/R9_layered_affinity_r9.py`, SHA-256 `2e6221b4e618d2007aa451db7466d6d985e6347135154f38f6cb46d47501f131`. The original attachment remains unchanged. This port is [layered_query_flow.py](../../../src/q3/layered_query_flow.py); it is **not connected to** the R8 solver or automatic strategy selector.

Public entry:

```python
construct_layered(graph, cores, *, capacity, cross_delay_cycles)
```

It returns `(plan, metadata, evidence)` or raises `GuardError`, a typed `UnsupportedStructure`. `plan` contains only `node_to_subgraph` and `core_schedules` with singleton eligible compute ops. The caller supplies the original graph, core count, physical `L1`/`UB` byte capacities, and cross-core delay; the function performs no file I/O, CLI work, Task/Step call, evaluator call, or candidate search. The row recognizer and ports are imported explicitly from this repository.

The algorithmic body was copied from the archived R9 source: Q/K/V projection and row anchors, stopped-frontier DSU and same-layer collision guard, phase assignment and original-edge checks, bounded two-pass subset DP, deterministic shared placement and priority words, static memory/path/traffic checks, and all original rejection conditions remain. The port removes the attachment's packet manifest, dynamic `sys.path`, runtime profiler, CLI, output writing and timing metadata. It adds parameter checks and calls the official **pure `validate_graph`** at `RawIndex.build` entry, converting its validation failure to `GuardError`. This tightens malformed-input behavior without changing valid graph semantics. It still deliberately rejects direct op→op edges, COPY-mediated compute dependencies, same-depth multi-key bridges, and other unsupported structures. Rejection is not evidence that the original P3 graph is infeasible.

The exact private-load partition uses O(K·3^r) time and O(K·2^r) cached states for `r≤10` tracks and K cores. The current within-phase ready scan is O(n²) worst case. No solver latency claim follows from the small tests. Static `step2_no_spill_certificate`, COPY traffic predictions and compute/FIFO path lengths are conditional on the port's assumptions; their match to the unmodified official Task/Step semantics has **not** been accepted here. The port has not been run on 005/086, and it has no official Makespan, M2/M3, G, cache, or full-500 evidence.

One local test invocation passed five synthetic tests:

```sh
python3 -m unittest discover -s tests -p test_q3_layered_query_flow.py -v
```

They compare the two-pass subset-DP proxy against exhaustive two-core grouping, require rejection of a same-depth dynamic join, and check typed rejection of malformed graph/capacity and an excessive core count. There were zero formal-graph constructor, Task, Step, E0/E1/E2 or pipe_bound calls. Root coordination will separately freeze inputs and decide whether to run a single 005/086 port reproduction; its output, if any, must remain separate from official evaluation and solver wall-clock acceptance.
