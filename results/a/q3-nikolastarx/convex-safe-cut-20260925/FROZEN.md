# Frozen H-envelope safe-cut trial

Exactly case 005, core 0, consumer 1289 (rank 202). `safe_cut.py` SHA-256 `4e2d49cf32cd8fc7a80b2bd2da9137c17542adbc00a1da6a2a9db4019abd0545`. Inputs: raw graph SHA-256 `c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f`; base R9 plan `2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a`; frozen convex-envelope guard result `7c234a2c347b1f94e163c5d0092b521465dd0facc294dc3343a6dc38a429f1ab`. Assignment cited HEAD `2c1e12ac4c55a920f62078d707d95fdf5f5eb100`, while `git rev-parse HEAD` during freezing read `03f594598259a8ad2162e8247d5a9c659c57c133` after concurrent repository activity. The script does not use live source code and re-hashes every input; this difference is recorded rather than concealed.

Rule: rebuild H from every original op arc and all five base compute-word adjacency arcs, check it matches the frozen guard's base node/arc counts and is acyclic. Apply the same maximum-last-exit propagation as the earlier single-core cutoff, now on H. If L<202, produce exactly one segment [L,202] and explicitly Kahn-check the full H quotient, retaining COPY ops as separate vertices; otherwise report singleton-only and emit no candidate. No parameter grid or other target.

One process, one worker, 60-second hard subprocess timeout, no retry, zero official Task/Step/E0/E1/E2/pipe_bound/constructor calls. After freeze, run exactly once under standard-library supervisor:

```sh
python3 - <<'PY'
from pathlib import Path
import subprocess,sys
base=Path('results/a/q3-nikolastarx/convex-safe-cut-20260925')
with (base/'stdout.txt').open('x') as out,(base/'stderr.txt').open('x') as err:
    p=subprocess.run([sys.executable,'-B',str(base/'safe_cut.py')],stdout=out,stderr=err,timeout=60)
print('exit',p.returncode)
PY
```

On first exception stop and retain logs. No old pilot run or Step1 call is part of this trial.
