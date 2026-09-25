# P1 memory-release key: synthetic contract probe

`src/review/p1_memory_key_contract.py` is a research-only adaptation of the
archived Pro R4 `src/reuse_prekey.py` and its `README.md` §2, from
`AI chats/P1多Pipe链构造证明/附件/r4-p1_r4_s6607/`. The R4 author supplied the
`release_word` construction and the tensor-ID-offset counterexample. This
local probe adds frozen-source checking, process binding, actual Step3 incidence
checking, and a bounded comparison; it does not claim authorship of the R4
argument or establish general cache correctness.

The key contains `Family.prekey`, the R4 tensor-rank/set-iteration word, hashes
of **every** frozen official `code/*.py` and `data/config.txt` file verified
against `docs/a/source-manifest.json`, local adapter hashes, and Python
implementation/version/hash metadata plus process ID. It also binds the actual
capacity and bandwidth: this probe uses **synthetic L1=80, UB=80,
bandwidth=60**, from the local fixture's `reproduce.py`, rather than the
official evaluation capacity. It is valid only in this
process, under the strict ordered, private, no-spill `Family` domain. Before
use, `memory_key` checks the actual prepared Step3 Task's input/output tensor
lists for each submitted compute op against the ordered original incidence.
This is a necessary premise, not proof that all unselected boundaries are
equivalent. The key deliberately preserves Python `set` iteration order.

The CLI requires the existing local
`results/a/p1-memory-cache-counterexample-20260925/` directory containing
`graph.json`, `plan.json`, and `reproduce.py`,
an output path that does not yet exist, and explicit `--execute`. It compiles
the two chain projections once each, then the complete original graph with two
Tasks: **four** official Step1/2/3 Task compilations total. It uses two
single-Task Fraction simulations and one whole-plan Fraction quotient call,
checks each projection against its complete-plan Task, and checks that the two
Tasks' old prekeys agree while their new keys and raw signatures differ. It
saves `report.json` with source/fixture hashes and attempted/completed calls.
There is no E0/E1/E2, solver, official case, or production cache integration.
The rational responses do not assert binary64 equivalence to E0.

This change only prepares that opt-in probe. No `--execute` run, Task compile,
or response evaluation has been performed for this version. A later run must
record its own outcome; the historical R4 report is not a local validation.
