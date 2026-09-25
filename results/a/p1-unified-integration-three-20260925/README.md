# P1 unified branch-refine integration: three cells

This package archives one completed fixed-solver run at commit `834d8c957538ee069c66aadac9509552a4cc69d7`, started 2026-09-25 15:07:55 UTC. It contains 3 of 500 required cells and is a diagnostic subset, not a full-submission result or full500 mean.

The three cells used the same `src.q1.branch_refine` solver. Runtime selection differed: 085 selected branch-aid; 075 and 016 selected parent. Each cell has its exact plan, graph/config, compressed diagnostic/E0 result/trace bytes, raw logs, and a derived per-cell receipt. The untouched batch receipt and launcher originals are retained. `MANIFEST_BASELINES.json` traces each denominator to the fixed full500 feed at commit `0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297`; the copied singlecore E0 result bytes and graph/config/official identities were verified against those feed pointers. No K1 multicore result was used as a baseline.

The feed preflight checks schema, artifact availability, and hashes only; it ran no solver or evaluator. E1 counts are 4 per cell (12 total), E0 counts 1 per cell, with E2 and retries zero. Environment inventory is limited to fields recorded by the runner; unknown CPU/GPU and OS cache state remain unknown.
