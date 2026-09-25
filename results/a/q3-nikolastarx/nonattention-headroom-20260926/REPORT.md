# P3 R9 non-attention headroom screen (read-only)

Frozen worktree HEAD: `7fccc879e53d0ffd06f521bd5c4ee43a229d7304`. Cohort: 78 coverage-rejected graphs from the 100-row static R9 coverage snapshot; 22/100 were recognized and excluded. The selection was frozen before raw graph inspection in `selection-freeze.json`.

Ranking uses K=5 only and per-case optimistic slack `B/L - B/T`: B is the same-graph official single-core baseline, L is the frozen global compute-only lower bound, and T is the current same-run Forest P3 best makespan. The 10 are ranked by descending unrounded slack, case ID breaks ties. This slack is only headroom to a loose bound; it is neither attainable improvement nor an official score/gain claim.

|Rank|Case|Ops (compute; raw total)|K5 B / L / T|B/L − B/T|Pipe lower bound / critical path|R9 rejection|
|---:|---:|---:|---:|---:|---:|---|
|1|044|1364; 1436|154407 / 14881 / 41205|6.628829|14881 / 7672|no closed attention query row matched|
|2|065|704; 914|53068 / 5904 / 11270|4.279698|5904 / 1265|no closed attention query row matched|
|3|015|1013; 1290|177362 / 20300 / 38938|4.182059|20300 / 7913|no closed attention query row matched|
|4|012|972; 1304|59088 / 7115 / 13175|3.819851|7115 / 2506|no closed attention query row matched|
|5|026|636; 769|99203 / 14154 / 30256|3.730044|14154 / 4319|no closed attention query row matched|
|6|010|667; 796|86969 / 11100 / 20608|3.614888|11100 / 3146|no closed attention query row matched|
|7|055|1236; 1468|118835 / 13810 / 23526|3.553776|13810 / 6962|no closed attention query row matched|
|8|096|1198; 1362|84194 / 10626 / 18812|3.447848|10626 / 9417|no closed attention query row matched|
|9|046|992; 1058|276455 / 41850 / 83050|3.277076|41850 / 28456|no closed attention query row matched|
|10|100|1394; 1654|151223 / 20402 / 33676|2.921638|20402 / 4830|no closed attention query row matched|

Pipe totals below include COPY ops (`PIPE_M` / `PIPE_V` / `PIPE_MTE2` / `PIPE_MTE3`); op histograms and raw graph SHA-256 values are in `top10-evidence.json`.

- `044` — `ADD:264, CONV:550, COPY_IN:61, COPY_OUT:11, RELU:550`; pipe counts M/V/MTE2/MTE3 = 550 / 814 / 61 / 11; contracted DIV parent-op signatures {}.
- `065` — `ADD:140, CONV:8, COPY_IN:153, COPY_OUT:57, DIV:65, EXP:16, MATMUL:59, MUL:50, NEG:18, REDUCE:150, RELU:127, SIGMOID:22, SQRT:6, SUB:43`; pipe counts M/V/MTE2/MTE3 = 67 / 637 / 153 / 57; contracted DIV parent-op signatures {"ADD": 12, "EXP,REDUCE": 16, "MATMUL": 16, "SQRT,SUB": 21}.
- `015` — `ADD:192, COPY_IN:211, COPY_OUT:66, DIV:76, EXP:13, MATMUL:130, MUL:112, NEG:26, REDUCE:241, RELU:106, SIGMOID:50, SQRT:10, SUB:57`; pipe counts M/V/MTE2/MTE3 = 130 / 883 / 211 / 66; contracted DIV parent-op signatures {"ADD": 20, "EXP,REDUCE": 13, "MATMUL": 13, "SQRT,SUB": 30}.
- `012` — `ADD:193, CONV:8, COPY_IN:251, COPY_OUT:81, DIV:84, EXP:10, MATMUL:127, MUL:99, NEG:24, REDUCE:214, RELU:92, SIGMOID:45, SQRT:11, SUB:65`; pipe counts M/V/MTE2/MTE3 = 135 / 837 / 251 / 81; contracted DIV parent-op signatures {"ADD": 22, "EXP,REDUCE": 10, "MATMUL": 10, "SQRT,SUB": 42}.
- `026` — `ADD:190, CONV:15, COPY_IN:102, COPY_OUT:31, DIV:6, EXP:3, MATMUL:87, MUL:10, NEG:8, REDUCE:88, RELU:215, SIGMOID:11, SUB:3`; pipe counts M/V/MTE2/MTE3 = 102 / 534 / 102 / 31; contracted DIV parent-op signatures {"EXP,REDUCE": 3, "MATMUL": 3}.
- `010` — `ADD:107, COPY_IN:93, COPY_OUT:36, DIV:14, EXP:7, MATMUL:131, MUL:48, NEG:19, REDUCE:110, RELU:177, SIGMOID:47, SUB:7`; pipe counts M/V/MTE2/MTE3 = 131 / 536 / 93 / 36; contracted DIV parent-op signatures {"EXP,REDUCE": 7, "MATMUL": 7}.
- `055` — `ADD:281, COPY_IN:173, COPY_OUT:59, DIV:56, MATMUL:91, MUL:102, NEG:32, REDUCE:261, RELU:318, SIGMOID:38, SQRT:7, SUB:50`; pipe counts M/V/MTE2/MTE3 = 91 / 1145 / 173 / 59; contracted DIV parent-op signatures {"ADD": 14, "SQRT,SUB": 42}.
- `096` — `ADD:233, CONV:9, COPY_IN:114, COPY_OUT:50, DIV:20, EXP:10, MATMUL:161, MUL:45, NEG:24, REDUCE:153, RELU:481, SIGMOID:52, SUB:10`; pipe counts M/V/MTE2/MTE3 = 170 / 1028 / 114 / 50; contracted DIV parent-op signatures {"EXP,REDUCE": 10, "MATMUL": 10}.
- `046` — `ADD:192, CONV:400, COPY_IN:58, COPY_OUT:8, RELU:400`; pipe counts M/V/MTE2/MTE3 = 400 / 592 / 58 / 8; contracted DIV parent-op signatures {}.
- `100` — `ADD:358, CONV:9, COPY_IN:171, COPY_OUT:89, DIV:78, EXP:3, MATMUL:100, MUL:156, NEG:33, REDUCE:291, RELU:238, SIGMOID:51, SQRT:8, SUB:69`; pipe counts M/V/MTE2/MTE3 = 109 / 1285 / 171 / 89; contracted DIV parent-op signatures {"ADD": 16, "EXP,REDUCE": 3, "MATMUL": 3, "SQRT,SUB": 56}.

## Structural families and recognizer failure

- **Conv/ReLU/Add residual DAGs (044, 046):** 400–550 CONV, the same number of RELU, plus 192–264 ADD; no MATMUL, DIV, EXP, or REDUCE. These cannot contain the exact attention query-row pattern sought by R9.
- **MatMul + EXP/REDUCE mixed graphs (010, 012, 015, 026, 065, 096, 100):** substantial MATMUL and elementwise/reduction mix, with variable CONV/RELU content. They are attention-like at the operator-vocabulary level, but not the closed query row required by R9.
- **MatMul/reduction without EXP (055):** 91 MATMUL, 261 REDUCE, 56 DIV and high vector work, but no EXP; separate mixed reduction family.

The R9 coverage file reports `recognize_layers: no closed attention query row matched` for all ten. The matcher scans DIV roots whose two contracted compute parents are ADD and then demands a precisely closed query-score-normalize motif. In these ten graphs, after COPY contraction, **none of the DIV nodes has two ADD parents**; the signature counts are recorded per case in the JSON evidence. This is a narrow necessary-gate mismatch, not proof that no useful affinity/decomposition exists.

## Initial construct proposal (superseded)

The proposal below was written before checking existing local mechanisms; retain it as analysis history, not as the recommended next step.

Add a COPY-contracted, attention-independent fork/join capsule builder: detect maximal convex work regions around actual graph joins (ADD/REDUCE/DIV and their producer-side M/V chains), expose exact tensor boundary ports, then construct the quotient and assign ready capsules by remaining critical-path work and current per-core load. It targets all three observed families with graph structure already present; it does not fabricate attention rows or sample random schedules.

A graph-only falsification gate for a first fixed-input test is: run against these ten frozen cases; each case must be partitioned exactly once into capsules, quotient must be acyclic, every original inter-capsule dependency must appear at capsule boundaries, and a deterministic five-core assignment must satisfy the existing plan validator without invoking E0/E1/E2. Failure on any case rejects the broad-coverage claim. That gate establishes coverage/legality only; official makespan, DDR and cache effects remain unmeasured and require separately authorized evaluation.

## Correction after checking existing mechanisms

The capsule-builder proposal duplicates the existing general fork/join chain-placement direction in [`src/q3/gap_dag.py`](../../../../src/q3/gap_dag.py), documented in [`docs/a/q3/GENERAL_GAP.md`](../../../../docs/a/q3/GENERAL_GAP.md). The shared-input continuous-pipeline mechanism in [`src/q3/shared_pipeline.py`](../../../../src/q3/shared_pipeline.py) is a narrower, separate construct; its local 044/046 capacity experiment already reports results in [`pipeline-capacity-two-shot-20260925/REPORT.md`](../pipeline-capacity-two-shot-20260925/REPORT.md). Therefore do not start another generic capsule builder from this screen.

The unresolved question is transfer and quality evidence: whether the already-existing guarded/gap mechanisms cover these ten under one fixed current solver, and what their case-level official makespan, DDR/cache behavior, and end-to-end solver time are. The Forest T values here are the frozen Forest baseline used only for slack ranking; they do not describe gap-DAG outcomes. R9's 78/100 recognition misses are not evidence that the general fallback cannot schedule those graphs. Resolve that distinction from existing fixed-version records first; any new E0 work needs its own authorization and fixed scope.

## Limits

This is a static prioritization and structural inspection, not an algorithm result. Global bounds are compute-only relaxations and may be loose; no lower-bound slack is interpreted as a forecast of achievable gain. No solver, Task/Step/evaluator, score, browser, or benchmark was run. Raw graphs were read only after the input hashes and deterministic selection rule were frozen.
