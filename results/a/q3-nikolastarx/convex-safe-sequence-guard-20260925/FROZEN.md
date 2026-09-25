# One-pass 194-op static sequence guard

Freeze at worktree HEAD `03f594598259a8ad2162e8247d5a9c659c57c133`. Script `static_guard.py` SHA-256 `cf9fb0754d9a067f1aa52b07d4040a88175d31738f6c18a999883bb7055c990c`. Input byte hashes: prepared `91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44`, base plan `2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a`, **194-op** candidate `549519032c0ae7b78957463d0b6189d30184bcfd46e06fa60fc2c1fcc7dc6615`, older 201-op regression plan `f4c58ccf77f5a8add20687eb20247ede169ff34b78a0f24e1c8bda805f1c75a2`, sole official Step1 result `25e3148631efc5a4186a980a8669c00d9e06756541de1f2c38fafe55e790781f`.

Imported pure helpers, with their `main` blocks uncalled: `convex-pilot-step1-20260925/step1_only.py` SHA-256 `ab029d2afc54d7ca415d2c2c835d987936a0fe9e049acc83d258fc4f314b675a`; `convex-sequence-guard-20260925/static_guard.py` SHA-256 `7c4116c6a076ccbba22725594a27a0c99aeed7cb08f27891985d1403ede80931`. Inspected, never called, official `_prioritize_task_seq` source `multicore_cut_evaluate_problem_2.py` SHA-256 `0b39f84d5ec0a7fba9a4c92a598a9044b97ab79c71393824c1ba130ecfe6c464`; official Step1 source `d8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034`, P3 source `eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0`.

The official priority function is a Python stable `sorted(raw_seq, key=rank.get(label, fallback))` followed by a topological check. The script first reproduces the archived old `task.seq` and the 201-op `candidate_seq` exactly from the sole saved `raw_seq`, then labels COPY ops for the 194-op plan and performs one pure stable sort. It checks all original local producer-consumer arcs, capacity intervals, other-core ownership/words/FIFO, and a five-core necessary union graph. No new Task/Step1/Step2/Step3/E0/E1/E2 calls or new Task reconstruction.

One process, one worker, 60-second hard wall, zero retry. Run from the worktree root:

```sh
python3 - <<'PY'
from pathlib import Path
import subprocess, sys
base = Path('results/a/q3-nikolastarx/convex-safe-sequence-guard-20260925')
with (base/'stdout.txt').open('x') as out, (base/'stderr.txt').open('x') as err:
    process = subprocess.run([sys.executable, '-B', str(base/'static_guard.py')],
                             stdout=out, stderr=err, timeout=60)
print('exit', process.returncode)
PY
```

On the first error retain evidence and report it; do not patch and rerun. A DAG pass would only mean the necessary graph is acyclic, leaving new core-0 Step3 memory edges and runtime behavior unresolved.
