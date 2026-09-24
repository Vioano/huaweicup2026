# Shared-input full-core candidate: P1 044/k3

This is one successful constructor plus one successful official E0, not an execution failure. E0 makespan is **68109 cycles**, compared with the provided v4 reference **64624** (+3485, +5.392733%). Scheduled DDR is **2957344 B**, compared with v4 **2026944 B** (+930400 B); spill is 0. The candidate regresses on both cited metrics and is not recommended for the unified algorithm.

Stage timings: solver 0.081385165976826102s; E0 0.14207645796705037s; total window 0.42171445797430351s. Calls: 1 constructor, 1 E0, 0 E1/E2/retries.

The portable runner is a derived copy, explicitly not the runner used for the recorded execution. Raw execution receipt and original runner remain in the parent folder. See [feed](board-feed-044-k3.json), [receipt](receipt.json), and [manifest](manifest.json).


Pre-release correction: the earlier public draft incorrectly referenced case 084 as the single-core baseline and pointed its log outside this package. This package now includes the verified case 044 baseline bytes from commit 0e0d7cd327c51cc6ac365e01f4b6a7d2b28f9297 (`baseline-044-singlecore.json.gz`, SHA-256 73f1d15fdea4f706b22099d2339a0e74a76c4114a68672077a98a8e15faa913c); its graph identity matches the evaluated case. The execution log is bundled as `e0.log`.
