# P2 fixed-owner solver: three-cell qualification

Frozen full solver `fcc7fa2410edb5e2cd3868b1b7f2d7bce82b58a9`, entry `src.q2_nikolastarx.adaptive_fixed_owner_guarded`, one fixed rule and four distinct oracle starts maximum. This is a qualification of the complete solver, not a full-500 benchmark or a new best-batch claim.

| Case K5 | Incumbent M | Selected M | Selection | Extra DDR bytes | Cold solver seconds | Independent E0 seconds |
|---|---:|---:|---|---:|---:|---:|
|006|22471|21896|fixed-owner retiming, -2.55885% M|556690|1.255181|0.215821|
|089|119306|119306|reject the 126166 candidate|954880|2.593462|0.475370|
|097|2102348|2102348|known unsupported structure, zero E2|21311488|0.412670|1.030208|

Selected plan canonical identities and complete official M/five movement fields/cross-task traffic match frozen expectations. These expectations were only checked after solver and E0, never used for algorithm decisions. On the first two cells, the unique selected native E2 record equals the independent E0 record exactly; 097 has an independent E0 only. All selected DDR values equal the saved incumbents.

One valid scoring window: 2026-09-25T15:39:14.408870Z to 15:39:20.441265Z; 7.102069 seconds including preflight. Three cold solvers, seven native E2/API calls, three independent E0, zero fallback or scoring retries. All six child exits are zero, no surviving or cleanup-killed processes; root post-scan empty, pressure1 and swap1231.12MiB unchanged. Timings are observed on shared macOS arm64/Python3.12.13, not exclusive-host latency claims.

An earlier producer attempt at15:35:37Z passed a manually mistyped interpreter path (`20250925` instead of `20260925`) and failed the identity preflight. It caused zero solver/E2/E0 and no run directory. The coordinator closed that gate and reissued an administrative v2 at unchanged scoring budget. Root extracted the exact pinned README command programmatically and recorded actual argv/stdout/stderr/PID. The earlier executor receipt's stderr field is a summary rather than verbatim stderr; see failure-root-readback.json. Original failure receipts remain in the archive and are not rewritten as success.

`originals.zip` preserves the complete plans/oracle plans/ledgers/results/traces/process receipts, producer package, both pending template and used v2 gate, expectations, and root readback. `archive-manifest.json` lists every member size/hash. The package and absolute paths are historical evidence, not a replayable approval. The earlier closed gate original is maintained by the coordinator; its hash is recorded here.

The included FIFO audit used only saved plans and no new construction/evaluation: candidate089 has a necessary FIFO lower bound123268 > incumbent119306, so a future proved-bound guard could avoid its losing E2 call. This pruning is **not** in frozen fcc. Equality cannot prune a possible DDR tiebreak, and unsupported bounds cannot prune.

Formal full500 remains c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f (K5 mean4.549756996698352). Qualification confirms adoption/rejection/fallback branches, not generalization or a significant improvement. Next decision requires preselected broader same-algorithm coverage and solver cost; no new full500 or other scoring authorization is implied.
