# Unified return v2: three-cell smoke export

This is a **3/500 P1 matrix preview** for the fixed v2 solver, not a full run, a full mean, or a mixture with v1. Source implementation `3fa0100c8bf9f4a7c1745f9d3f925748ac3fdc19`; actual runner `970ef7edc8cbba728d13298f7dacb30c1b323008`. The batch completed with 3 solver starts, 9 internal E1 calls included in solver wall, 3 separate external official E0 calls, zero retries, and confirmed cleanup. All selected E1 winner Makespan and complete movement objects matched external E0. Export added zero scoring calls.

| Case | Selected | E0 Makespan | Solver wall s | External E0 wall s | E1 calls | Official singlecore E0 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 008 | bounded | 100603 | 0.5062539589998778 | 0.14470929201343097 | 3 | 487605 |
| 084 | capacity-return | 399121 | 4.352873833006015 | 1.754062416992383 | 3 | 2507412 |
| 095 | bounded | 420852 | 1.5032732499821577 | 0.753205707995221 | 3 | 2084853 |

The board feed references plan bytes copied unchanged, full result and trace bytes held losslessly in gzip, and a path-redacted run derivative. Original hashes are in `export-receipt.json`; the original run receipts and other process logs remain only in the local batch directory and are not claimed as Git archived. Official singlecore results were copied from frozen commit `6fcec11ccc472a1a652b21feb6fccf85a4555598` after graph/config/source identity checks. The batch receipt did not retain the runner launcher argv, so the feed leaves that list empty rather than reconstructing an unobserved command.

The read-only board precheck checks format and available bytes only. It does not rerun official E0 or establish full-matrix algorithm quality.
