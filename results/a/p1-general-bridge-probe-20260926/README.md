# P1 general bridge static probe (2026-09-26)

This is a research-only structural prototype on branch `codex/p1-general-bridge-20260926`, parent HEAD `a1bb4451cd85c46b32bb928d57c81e22cfeca1a6`. Source SHA-256: `src/q1/general_bridge_probe.py` = `a01a816e4b86992d696e976685bd2678f9486fd48f7e6738071a15a4e8d9a005`; test SHA-256 = `101810f80d23d3aa22b4e7da057cf8c09c8745892be61f9e13269eefc462c705`. Python 3.14.5 on macOS. No commit or push was made.

The constructor reads only the current graph and supplied baseline. It examines all donor Tasks for the existing `branch_aid._witness` X/Y/J certificate, checks exact original Task coverage, ranks positive Task-local Pipe peak reductions, and inserts one X on a different core at a feasible slot. It checks the complete contracted Task data graph plus adjacent same-core order edges for acyclicity, then calls the official `derive_multicore_plan` and `validate_task_order`. The donor, helper, and slot are chosen by the recorded structural key: greatest Task-local Pipe peak reduction, least added static COPY service/bytes, least adjacent helper Pipe work, then stable Task/core/slot IDs. No case ID, saved result, Makespan, or evaluator score enters this rule.

Representative read-only inputs, chosen to include a baseline rejected by the old height rule and a known bridge-shaped larger graph:

| Cell | Original graph in frozen ZIP | Baseline plan source | Graph SHA-256 | Baseline plan bytes SHA-256 |
| --- | --- | --- | --- | --- |
| 068/K5 | `data/raw/a/official-cases.zip:data/case_068.json` | `results/a/p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500/cells/068-k5/originals/plan.json` | `dfd9a58ef9d26a8a4567026b50af8b4499d87eebb3d98f8208b909b11e963c6d` | `b35d39058eb3a812e935a724f8451498cb4861ac108f4be1035d5bbc59adfb8d` |
| 085/K5 | `data/raw/a/official-cases.zip:data/case_085.json` | `results/a/p1-r6-pilot-20260925/official-085-k5/base-plan.json.gz` (decompressed JSON) | `b63169e9cd0f21dc2da6617e7138472e95937465c703b7e4bf4dbc80125ed4f6` | `e7b3e907ec10ef3d5acc55682200735c42c0f38e4b72da1372c2363b7f01c4d8` |

Reproduction from the repository root in zsh:

```sh
python3 -m unittest tests.q1.test_general_bridge_probe -v
python3 -m src.q1.general_bridge_probe --graph <(unzip -p data/raw/a/official-cases.zip data/case_068.json) --base-plan results/a/p1-branch-refine-full500-20260925/20260925T1525Z-s6607-branch-full500/cells/068-k5/originals/plan.json --cores 5 --output-dir results/a/p1-general-bridge-probe-20260926/068-k5
python3 -m src.q1.general_bridge_probe --graph <(unzip -p data/raw/a/official-cases.zip data/case_085.json) --base-plan <(gzip -dc results/a/p1-r6-pilot-20260925/official-085-k5/base-plan.json.gz) --cores 5 --output-dir results/a/p1-general-bridge-probe-20260926/085-k5
```

The three tests passed. Timed runs with already extracted input files took 0.39 s for 068/K5 and 2.36 s for 085/K5 (`/usr/bin/time -p`, includes Python startup, JSON reads, structural selection, output writes). First unoptimized 085/K5 attempt reached the 10 s soft limit; reusing its quotient Task data edges across insertion slots reduced it to 2.36 s. A local test initially contained a mistaken expected schedule shape; corrected before final passing run. These were development attempts, not evaluator attempts.

| Cell | Static census | Chosen donor → helper/slot | Task-local raw Pipe peak decrease | Extra static COPY | Candidate plan SHA-256 |
| --- | --- | --- | ---: | --- | --- |
| 068/K5 | 61 old Tasks, 29 bridge witnesses, 281 acyclic slots | Task 38/core 0 → core 4/slot 5 | 4,008 cycles | 22,274 B; 381 normalized service cycles | `0b4b64cba1e0000220337bcee60cd94e206526f949ec3ba04cad02fb4d8b2720` |
| 085/K5 | 97 old Tasks, 50 bridge witnesses, 477 acyclic slots | Task 96/core 4 → core 3/slot 19 | 19,216 cycles | 20,738 B; 352 normalized service cycles | `ba9be0e9bea3ea3f23c0eda28c7fa6ce1d5787fa52624da8e54a9c61120cc054` |

Both plans contain exactly the official two keys and pass the official structural plan/order validators. The static COPY account excludes Task compilation and Step2 spill. Raw Pipe work reduction is a selection proxy, not a Makespan prediction. Task compilation, FIFO/MEM execution, capacity, spill, E1, E0, E2, and end-to-end solver quality remain unverified; scoring calls were zero. Neither cell contributes to formal results or the 100×5 matrix.
