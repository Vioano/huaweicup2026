# Baseline evidence revisions

This directory adds revision 2 for three existing attempts. Each revision attaches an unchanged gzip result for the official E0 single-core A baseline. It does not create a new measurement. The attempt's Makespan, plan/result/run references, and null end-to-end solver wall time are retained.

The read-only donor is commit `f26704ed8748f0a575b55f1a02b83d7335a1083f`, under `results/a/q3-yuanzhifang/board-na-audit-20260925/`. Its README and `diagnosis.json` were read with `gh api`. I also read the existing baseline feed records at their fixed commits and verified their result SHA-256 and graph/config/official identity against each target attempt. These fixed-source observations are recorded separately in `source-audit-20260925.json`; the exporter does not recreate or claim to rerun them.

The three result files are byte-for-byte copies of the donor gzip files:

| Case / attempt | Baseline Makespan | Gzip SHA-256 |
| --- | ---: | --- |
| 044 / `nikolastarx-pipeline-capacity-044-k5-20260925-s3172` | 154407 | `73f1d15fdea4f706b22099d2339a0e74a76c4114a68672077a98a8e15faa913c` |
| 046 / `nikolastarx-pipeline-capacity-046-k5-20260925-s3172` | 276455 | `d34869c92f2f414dfe9c6f1bf715e0c26f4f2438c8f8cb4840868b9199b6997f` |
| 097 / `nikolastarx-leaf-tile-097-k1-20260925-s3172` | 11491509 | `bfd1fddfe03ac16242562d8849fc9e21f82a179ee1b25c13d7b21126888af534` |

`export.py` is a deterministic local exporter. Run it from any directory inside this worktree; it checks the original feed blob IDs, attempt IDs, null baseline, revision, target identities, gzip hashes, and decoded single-core result fields before writing the feed and `verification.json`. Inputs are the original feeds at the paths recorded in the script and these three copied gzip files. It performs no evaluation or network request. `verification.json` contains only checks executed by the exporter.

The author worktree does not contain `src/benchmark_board/protocol.py`. Preflight used the main project's read-only validator with the author worktree supplied as `--repo`, so feed-relative artifacts resolved against this worktree. The actual command and captured result are in `protocol-preflight-20260925.json`. The exporter never writes or fabricates a preflight receipt; rerunning it leaves both the source audit and preflight receipt untouched.
