# Actual-compiler synthetic cache check

Fixed source `2587a0c1374a93bbbfe3540ffaf4e741b8dfb6d1`, locked Python 3.12.13, local macOS. This tiny synthetic experiment uses two four-operation private chains, L1=UB=80 bytes and bandwidth60; those capacities are not the official case configuration.

Eight cache requests produced **3 misses and 5 hits**. The two full chains correctly remained different entries despite their old prekeys matching. Two distinct final-M node IDs shared one new key and hit the same response. Four independent uncached Task compilations agreed with all four cached signatures and traffic records. Total: **7 actual static Task compilations, 0 response simulations, 0 solver/E0/E1/E2, no retry**; whole subprocess wall 0.148428s.

This supports one cross-ID hit plus rejection of the known unsafe old-key collision. It is not general equivalence, production adoption, or measured full-solver speedup. Per-request timings include conservative repeated source-scope hashing and must not be reported as pure compile cost.

The report records the actual request ledger, source-scope identity and fixture hashes. `manifest.json` explains the one local-executable-path redaction and retains original/public hashes. Existing fixture originals remain in `results/a/p1-memory-cache-counterexample-20260925/`.
