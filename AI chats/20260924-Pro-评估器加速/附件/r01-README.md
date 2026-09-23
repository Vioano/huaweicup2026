# Q1 evaluator breakthrough — bounded research artifact

**Status: mechanism prototype, NOT an E0 replacement, NOT a released new E1, and NOT proof of the user's end-to-end 10×/quality gates.** No repository was modified. No official graph was executed in this container. All runtime inputs here are explicitly synthetic **already-compiled task descriptions**; official Step1/2/3, raw graph validation, spill insertion and official capacity/lifetime validation were NOT executed. Runtime fixture metadata is not official memory/traffic evidence.

## Source identity and actual access

Authorized GitHub connection successfully read `Vioano/huaweicup2026` at the requested refs. `reference/scene_a.py` is the complete text of `src/eval_exact/_scene_a.py` at `5bfe53a29c1ba05167239f51ea937e602f7f85b4`, reconstructed locally and independently verified against its Git blob ID:

- bytes: 15150
- Git blob SHA-1: `985be6b26d6d502fef7cb9cbb7e53858e3697b7b`
- SHA-256: `603807adea832b6514d86f5e79107eafc8386eaacf9ee2c9e3f6fb2db705afc9`

The official collection hash stated in the project is `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`. The entire official source collection was NOT reconstructed and rehashed here. No ZIP from another conversation was accessed. A later authorized directory read identified the real `data/raw/a/official-cases.zip` (15,375,730 bytes; SHA-256 `e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528`). The extracted case_002.json is not a directly available file at that ref. Transfer of the authorized archive to the runtime failed (download-tool URL gating, then container DNS failure). This is NOT a repository-permission finding. Official full graph bytes, all official modules, old dev64 compressed truth and the new E1 raw benchmark results were not assembled in the local runtime.

Full texts read: P1_BATCH.md, new E1 results README, batch.py, _scene_a.py, problem1.py, pool.py, _official.py, official config.txt, evaluation_validation.py, and old event_model.py. Partial reads: official P1 lines 1–320; Step2 lines 180–405; Step3 lines 1–235 and 600–end; stub lines 1–225; source-manifest prefix and tail; scripts/a_materials.py (full); APPROXIMATIONS and ACCELERATION_HANDOFF long prefixes (connector output truncated). These partial reads must not be described as complete-file byte verification.

## Mechanisms implemented

1. Pack prepared task data into immutable NumPy numeric buffers: operation IDs are dense indices, original (task_id, op_id) comparison order is separately retained. Original current successor iteration order is retained. Physical incarnation and memory-reuse semantics must come from the verified official prepared input, not be re-derived by this kernel.
2. C++17 global replay uses one active task per core, one FIFO head per pipe, one running operation per pipe, integer predecessor counts and compact mutable state. No dynamic Python object graph in its event loop. It retains every global DDR clock cut and the order/expressions of binary64 work advancement and projection.
3. Optional coalescing removes intermediate DDR **projections within an issue phase**, not DDR work updates, retirements, or event times. Full debug audit retains the serial projection snapshots.
4. A separate Python no-DDR longest-path implementation demonstrates a strictly guarded exact algebraic special case. It rejects any shared-DDR operation and makes no speed claim.

The research API is **typed prepared-task input**, not the raw official API. `CandidateError` is not an official exception. Unsupported numbers/core limits/overflow bounds/native errors must be sent to E1 for the official result/classification. This fallback integration is proposed, not implemented or cost-measured here. Graph/partition/config/source/ABI changes invalidate the appropriate prepared handle. Arbitrary untrusted pointers must never be passed to the FFI.

## Build and reproduce

Environment actually used: Linux x86_64; CPython 3.13.5; GCC/G++ 14.2.0; NumPy 2.3.5; psutil 7.2.2. The container exposed five CPU IDs. Benchmarks pin to CPU 0, resource tests to CPUs 0 or 0–1. See `results/environment.json`. This is not a macOS/ARM/Windows result. No platform-independent speed extrapolation is valid.

```sh
# In an independent directory, with Python and the listed dependencies:
export PYTHONHASHSEED=0 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
g++ -std=c++17 -O3 -fPIC -shared -fno-fast-math -ffp-contract=off \
  -Wall -Wextra src/replay.cpp -o src/libreplay.so
python make_ablation.py
python run_tests.py
python clock_cut_probe.py
python clock_cut_event_probe.py
python clock_cut_l1_probe.py
python maxplus_no_ddr.py
for family in compute mixed ddr_heavy burst; do
  python benchmark.py --family "$family" --repeats 3
done
for engine in reference_global_full native_coalesced; do
  for workers in 1 2; do
    python resource_probe.py --engine "$engine" --workers "$workers"
  done
done
```

Run copies in a new directory: these scripts overwrite their own corresponding generated result file. Do not overwrite the delivered evidence when obtaining a new run. Archive the entire copy and its new hashes. Dynamic library supplied is Linux-specific; rebuild for the target machine. Compiler/toolchain changes require rerunning differentials. Default round-to-nearest is checked in the C++ kernel. The entry adapter deliberately rejects float waits, oversized times, and more than 128 cores; official API acceptance is broader, so those cases require fallback rather than an `invalid` label.

## What was actually tested

- `run_tests.py`: 365 synthetic compiled-task/candidate fixtures (5 targeted + 120 seeds × 3 schedule variants), unchanged new-E1 global replay vs quiet Python and both native variants. All operation/task start/end times match. Serial native debug mode also matches every DDR-issue projection snapshot. This is not complete official-object/exception equivalence and not 365 raw official graphs.
- `maxplus_no_ddr.py`: 72 additional synthetic compiled no-DDR fixtures, all operation/task timestamps match native replay. Python graph-DP performance was not benchmarked.
- `clock_cut_probe.py`: arithmetic witness that removing intermediate compute-event DDR updates can change an integer projected end by one cycle. The real-number expressions are equivalent, the binary64 paths are not. This is a helper-state witness, not a raw E0 graph counterexample or a measured Makespan error.
- `clock_cut_event_probe.py`: actually executes an eight-operation compiled-state witness against unchanged new-E1 global replay, both native variants, and an explicitly WRONG clock-cut-deleting mutant. Correct Makespan 33,554,532 versus mutant 33,554,531. This large-work witness does not establish reachability under official fixed capacities.
- `clock_cut_l1_probe.py`: a second actually executed compiled-state witness uses 480,000-byte L1 tensors (below the official 524,288-byte L1 capacity), 8,000-cycle transfers and 828 one-cycle clock cuts. Correct Makespan 32,725 versus mutant 32,724; both native variants match correct per-operation times. Its proposed raw graph and plan are saved with `UNEXECUTED_` filenames: frozen local compilation has NOT been run, so official reachability remains unverified. These one-cycle differences disprove bitwise equivalence, not the possibility of meeting a 1%/3% approximation target.
- `benchmark.py`: four synthetic graph families, 64 distinct schedule candidates per family, three repeats. All 24 execution-order permutations are used eight times. Baseline is **only the new E1 global simulator on supplied prepared tasks**. Neither path includes official raw validation, Step1–3, E1 pickle restoration/set rebuilding, input parsing or process startup. Native timings include typed candidate validation, fresh buffers and FFI. No cached answer is used. All candidate hashes/raw per-call wall and CPU times are saved.
- Quality in these four constructed pools: zero numerical/timestamp differences; all four top8 sets retain the pool optimum. This is not evidence for a 95% success probability on independent official graph pools. `ddr_heavy` has 29 candidates within 1% of optimum, of which 21 are outside its size-eight shortlist; that is unavoidable truncation, not a hidden claim that every good candidate is retained.
- `resource_probe.py`: same synthetic mixed pool, 64 distinct candidates, bounded one in-flight per worker, 1/2 spawn workers. Init/warmup, steady batch+IPC, shutdown, CPU and RSS are separated. Four resource runs' Makespans also cross-match. These are single observations, not replicated confidence intervals. Cold wall begins with an already-loaded parent/input; it includes child process startup/imports but not parent interpreter startup/input parsing.

`results/pilot_cyclic/` retains two **superseded** pilot results. They used a cyclic order biased toward one native variant's immediately following the other. They were not used in the final speed table. The corrected final CSV/summary files use the balanced protocol. Negative/overhead findings have not been deleted.

## Interpretation

Native global replay is strongly promising; this package does **not** measure the user's requested new-E1 end-to-end 10×. The remaining high-priority work is an immutable graph/partition preparation API: amortize static validation and partition derivation, avoid per-candidate pickle decoding/set reconstruction, and avoid full output construction in the private search adapter. Every new schedule still requires coverage and union dependency/core-order cycle checks.

Under the equal-average-cost model, a 64→8 pipeline which re-evaluates all eight with the CURRENT E1 has at most 8× end-to-end speedup even if initial screening is free. This is NOT a universal bound for heterogeneous candidate costs: the exact screening-free upper bound is total all-pool E1 cost divided by total shortlist E1 cost. The shortlisted candidates may be cheaper or more expensive than the pool average. The exact shortlist must also use an accelerated exact path, or reuse already-certified exact all-pool scores. Final E0 confirmation, audit and fallback costs must still be charged.

## Unexecuted official integration driver

`official_probe.py` is **syntax-checked only**, for an independent clean worktree at the fixed new-E1 commit. It accepts at most three distinct official plans sharing the same ordered mapping. It compares full E0/new-E1 objects, then all operation/task timings and DDR projections from the native kernel. Native timing is hot prepared replay; the script separately records extraction/packing, and explicitly does not claim a cold-native local-compilation measurement.

```sh
python official_probe.py --repo /path/to/frozen/worktree \
 --graph /path/to/case_002.json \
 --plans /path/to/plan_1.json /path/to/plan_2.json /path/to/plan_3.json \
 --output /path/to/new-unseen-output.json
```

Minimal upload to permit official execution in this conversation: complete `src/eval_exact/`, **all** frozen `data/raw/a/official/code/*` (loader hashes the whole collection, including files not researched here), official `config.txt`, `docs/a/source-manifest.json`, two or three graph JSONs such as 002/003/008, and up to three distinct same-partition official plans for each graph. Include `pyproject.toml` and `uv.lock` for the original dependency identity. Include current tests only if full existing-regression execution is desired. No 100-graph archive, historical 295 results or old dev64 pool is required for this bounded check.

## Files

- `reference/scene_a.py`: byte-verified frozen new-E1 global source.
- `src/replay.cpp`, `replay_api.py`: executable research kernel and adapter.
- `reference/scene_a_quiet.py`, `make_ablation.py`: reproducible log/output-construction ablation; no source edits to the reference.
- `fixtures.py`, `inputs/`: explicitly synthetic prepared inputs, seeds and candidate plans.
- `results/*.csv`, `results/*.json`: unrounded raw observations and summaries.
- `official_probe.py`: unexecuted bounded real-repository integration driver.
- `DESIGN.md`: decision, invariants, cache invalidation, cost model and release protocol.
- `MANIFEST.json`: SHA-256 inventory of delivered files (excluding itself and temporary bytecode).
