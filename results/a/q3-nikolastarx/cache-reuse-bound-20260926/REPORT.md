# P3 cache reuse bound: five fixed k=5 cases

Read-only analysis of the frozen E0 `result.json.gz` event streams. Cache key was treated as `tensor_id`; all events for a key had invariant `size_bytes`. Replay validated event chronology, resident hits, insert/eviction accounting, recorded `used_bytes`, final occupancy, capacity, and hit/miss byte totals against `cache_stats`. No evaluator was run.

The reproducible repository source is fixed commit `bff88a66cd76ceb2d75242bf99d34bfe8b1879d4`, under `results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/`. The local absolute paths below locate the same five frozen files on this host; their SHA-256 values identify the bytes independently of worktree location. The five rows are a **sample of one Forest500 solver**, not a new full-500 algorithm result.

| Case | Misses first time (forced) | In-flight repeated misses | Re-miss after insert | Total repeat-miss opportunity | Recorded hits | Capacity | Event SHA-256 |
|---|---:|---:|---:|---:|---:|---:|---|
| 005 | 342 / 651318 B | 101 / 144004 B | 0 / 0 B | 101 / 144004 B | 344 / 674612 B | 1048576 B | `161f6c00a3c406c3e11d9aead620c9652bdce4c8999ce1039c83000dd859f631` |
| 044 | 182 / 1036000 B | 0 / 0 B | 0 / 0 B | 0 / 0 B | 24 / 1585152 B | 1048576 B | `83a869d41f0aa66d9b06c6b2e5dac66a1b280c7f39e0d8bb4562678c3acf0594` |
| 065 | 153 / 299720 B | 6 / 27648 B | 0 / 0 B | 6 / 27648 B | 9 / 28080 B | 1048576 B | `eb4f51e8e0f0982ce382357c76bae984d720e33f039d42fde2ea70ba231d172e` |
| 071 | 83 / 166662 B | 16 / 31970 B | 0 / 0 B | 16 / 31970 B | 78 / 133360 B | 1048576 B | `7938a4d580af4e2a29632eba6a3c2dedc031a0976029126429472abdf7dc1c6c` |
| 086 | 358 / 669606 B | 88 / 140548 B | 0 / 0 B | 88 / 140548 B | 398 / 748628 B | 1048576 B | `978dcbc47485e412daaf709bd84093bfe8b20f13a4a1424b059d2730608275ce` |

Counts are `COPY_IN` requests. “First forced miss” means first observed request for that tensor key; the log alone does not establish whether alternate scheduling would make that key resident before use. “In-flight repeated miss” means another miss for the same key appeared before an insert event. “Re-miss after insert” means a prior insertion existed, but the later request was still a miss; it may reflect eviction or timing/retirement behavior. Those two repeated-miss classes are the directly visible candidate opportunities; their bytes are the requested tensor sizes, not guaranteed saved DDR traffic. Recorded hits are shown separately and are already converted.

## Interpretation

Case 065 does have nearly unique keys: 153 distinct tensor keys across 168 COPY_IN requests (91.1% of requests are the first demand for a key). Of its 15 repeated requests, 9 are recorded hits and 6 are in-flight duplicate misses, totaling 27,648 requested bytes. The cache ends at 299,720 / 1,048,576 B and the replay finds no evictions. This supports low reuse as the main explanation for its low byte hit rate (28,080 / 355,448 = 7.9%, low G); the remaining direct schedule opportunity is small. In particular, tensor 3 has simultaneous requests from all five cores before its one insertion. This points to key uniqueness and timing, rather than capacity pressure, as the observed limitation.

Cases 005 and 086 have substantial cross-core duplicate requests and repeated keys in the miss stream. This supports investigating schedule ordering as a bounded mechanism hypothesis: make a completed insertion visible before equivalent consumers issue COPY_IN, while preserving dependencies and resource constraints. The CSV reports count and requested bytes, not a replay of a reordered schedule.

## Bound and limits

This is an event-log upper-bound inventory, not a predicted M3 gain. Converting an in-flight duplicate miss requires the first transfer/insert to complete early enough and the consumers to be schedulable afterward; it may serialize COPY_IN and increase makespan. Converting a post-insert re-miss requires the entry to remain resident under the actual FIFO capacity/eviction and all concurrent insertions, and must preserve scheduling legality. Reordering can change eviction order, cache completion/retirement, DDR contention, operation start times, and M2. Therefore neither miss bytes nor their sum imply fewer actual M3 cycles or unchanged M2. A causal claim needs a separately frozen/legal reordered plan and full official E0 evaluation.

## Inputs

- `/Users/nikolastar/.codex/worktrees/p3-forest500-s59ee-20260925/huaweicup2026/results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/s01/cells/005-k5-unified-forest-witness-e0/evidence/result.json.gz` — 170747 compressed bytes, SHA-256 `161f6c00a3c406c3e11d9aead620c9652bdce4c8999ce1039c83000dd859f631`; 1129 events; capacity 1048576 B; final replay occupancy 651318 B.
- `/Users/nikolastar/.codex/worktrees/p3-forest500-s59ee-20260925/huaweicup2026/results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/s05/cells/044-k5-unified-forest-witness-e0/evidence/result.json.gz` — 51258 compressed bytes, SHA-256 `83a869d41f0aa66d9b06c6b2e5dac66a1b280c7f39e0d8bb4562678c3acf0594`; 388 events; capacity 1048576 B; final replay occupancy 1036000 B.
- `/Users/nikolastar/.codex/worktrees/p3-forest500-s59ee-20260925/huaweicup2026/results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/s07/cells/065-k5-unified-forest-witness-e0/evidence/result.json.gz` — 26779 compressed bytes, SHA-256 `eb4f51e8e0f0982ce382357c76bae984d720e33f039d42fde2ea70ba231d172e`; 321 events; capacity 1048576 B; final replay occupancy 299720 B.
- `/Users/nikolastar/.codex/worktrees/p3-forest500-s59ee-20260925/huaweicup2026/results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/s08/cells/071-k5-unified-forest-witness-e0/evidence/result.json.gz` — 30701 compressed bytes, SHA-256 `7938a4d580af4e2a29632eba6a3c2dedc031a0976029126429472abdf7dc1c6c`; 260 events; capacity 1048576 B; final replay occupancy 166662 B.
- `/Users/nikolastar/.codex/worktrees/p3-forest500-s59ee-20260925/huaweicup2026/results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/s09/cells/086-k5-unified-forest-witness-e0/evidence/result.json.gz` — 204945 compressed bytes, SHA-256 `978dcbc47485e412daaf709bd84093bfe8b20f13a4a1424b059d2730608275ce`; 1202 events; capacity 1048576 B; final replay occupancy 669606 B.
