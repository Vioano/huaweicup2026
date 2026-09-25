# P1 Colab migration evidence

`migration-evidence.tar.gz` preserves the successful two-cell Colab run and migration receipts. SHA-256: `9d4fb3b4610614c45f34b13a81115da63fc52ff320245f7e820369d548a16728` (154,575 bytes). Its manifest lists 53 payload files; each file's byte count and SHA-256 was independently checked against both the archive and extracted evidence.

## Frozen run and results

- Solver: `3a1b82b71ca1ff6689eb8e72f17d26c48b52073c`
- Colab wrapper: `bd6dc85a0b69f30d08714cbb46200f90632bb2d7` (SHA-256 `589cf9a544b3edfe31b3b515d5bdf9ec876badda52f3a26310af8640d5baa4e9`)
- Case 001, 5 cores: Makespan 47,502 cycles; DDR 1,644,160 bytes; solver 0.717 s; fresh official E0 0.516 s; plan SHA-256 `f580d0bd401b7f759b7abe65121c1f13eddf24ee99c3ec263bd65dafa7949ac8`.
- Case 051, 5 cores: Makespan 231,551 cycles; DDR 9,437,954 bytes; solver 3.732 s; fresh official E0 0.867 s; plan SHA-256 `d7de42f7eea7ca83787244b2307448d6d34b5b61045fd902fb2a97540b8ed5e2`.

Both plan hashes match the local two-cell pilot. This is a two-cell sample, not a full-set result or a new full-set mean. The run used 2 solver calls, 4 E1 calls, 2 fresh E0 calls, 0 E2 calls, and 0 retries.

## Migration and contract checks

The first sparse-checkout preflight failed before dispatch: 0 solver and 0 E0 calls. The CLI compatibility fix was confined to the tool environment and used Google’s official fork at [`f18e982c3265df5e923aa9def101ab3fd737e139`](https://github.com/googlecolab/jupyter-kernel-client/tree/f18e982c3265df5e923aa9def101ab3fd737e139); the successful run then completed both cells.

The synthetic TinyTask / Fraction contract check completed 4/4 TinyTask compiles and 3/3 Fraction responses. All five checks passed: `old_prekey_equal`, `memory_key_differs`, `raw_signature_differs`, `projected_keys_match`, and `projected_signatures_match`. These are contract checks, not E0 results.

The archive contains run receipts and derived evidence; it does not include user-uploaded input originals or credentials.
