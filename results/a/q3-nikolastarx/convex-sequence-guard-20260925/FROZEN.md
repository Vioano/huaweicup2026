# Frozen one-pass static guard, 201-op convex candidate

Frozen at repository HEAD `03f594598259a8ad2162e8247d5a9c659c57c133`. Script `static_guard.py` SHA-256 `7c4116c6a076ccbba22725594a27a0c99aeed7cb08f27891985d1403ede80931`. Inputs are the archived prepared snapshot `91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44`, old plan `2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a`, **201-op** convex pilot plan `f4c58ccf77f5a8add20687eb20247ede169ff34b78a0f24e1c8bda805f1c75a2`, and saved one-call Step1 result `25e3148631efc5a4186a980a8669c00d9e06756541de1f2c38fafe55e790781f`. The script verifies each byte hash before analysis. Official config SHA-256 is `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`; expected capacities are L1 524288 and UB 131072 bytes.

Exactly one static process, one worker, 60-second hard timeout, zero retries, zero Task/Step/E0/E1/E2 calls. The analysis reads the saved Step1 candidate sequence and reconstructs core 0 edges from `step2[0].ext_edges`, excluding the 730 old Step3 memory edges; other cores retain their archived graph and FIFO. It forms the five-core op DAG with tensor contraction preserving every producer, all cross links, and one DFS cycle witness when applicable. It computes conservative inclusive tensor live-interval peaks; a within-capacity result only supports no-spill capacity sufficiency under this interval model and is not a runtime memory peak. New core 0 Step3 memory edges remain unknown.

One-pass dispatch from the worktree root:

```sh
python3 - <<'PY'
from pathlib import Path
import subprocess, sys
base = Path('results/a/q3-nikolastarx/convex-sequence-guard-20260925')
with (base/'stdout.txt').open('x') as out, (base/'stderr.txt').open('x') as err:
    process = subprocess.run([sys.executable, '-B', str(base/'static_guard.py')],
                             stdout=out, stderr=err, timeout=60)
print('exit', process.returncode)
PY
```

On the first error retain stdout/stderr and partial artifacts; repair the script for handoff but do not retry this frozen process. The newer 194-op candidate is outside this run.
