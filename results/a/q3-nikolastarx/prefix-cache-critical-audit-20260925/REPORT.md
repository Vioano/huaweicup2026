# Case 044 P3 cache-event audit (read-only)

## Result

The prefix plan reaches the maximum possible hit bytes for its **fixed set of cache-keyed COPY_IN transfers**. Official P3 reports 182 eligible reads: 171 first reads of distinct logical tensor keys (1,012,064 bytes) and 11 later reads of those keys (11,264 bytes). Every first read missed; every later read hit. Thus the byte hit rate is 11,264 / 1,023,328 = **1.100722349%**. All 171 missed keys were inserted after their reads completed. There were no evictions, no repeated-key misses before fill, and no oversize keys (largest: 73,728 bytes). All distinct keys together use 1,012,064 of the 1,048,576-byte cache, leaving 36,512 bytes.

The 11 reused keys are `1000000125 + 126n` for `n=0..10`; each has exactly two reads of 1,024 bytes, one miss then one hit. In the prefix result, the misses are on core 1 at cycles 11,351–18,918 and the hits on core 4 at 20,574–36,144. The events alone do not identify an additional unserved repeated read.

The older capacity plan has the same 171 cache keys and sizes, 11 hits, 171 misses, and zero evictions; its official P3 makespan is 38,390 cycles. The prefix plan is 38,024 cycles, 366 cycles lower. That improvement happened with identical cache hit/miss counts and bytes. It is evidence for a scheduling/timing improvement, not evidence of increased cache reuse. A no-L2 counterpart for the prefix plan was not evaluated here, so its `G=M_B/M_C` and the change in `G` remain unknown.

## Scope of the conclusion

The frozen evaluator uses a logical tensor ID as the cache key, checks the cache when a COPY_IN issues, inserts on COPY_IN completion, and evicts FIFO only when insertion exceeds capacity. For the **observed transfer-key multiset**, an initially empty cache must miss on each key's first read. The total sizes of all unique keys fit in capacity, so an ordering that avoids overlapping same-key reads can hit on every later read; the prefix ordering already does. Merely reordering these same reads cannot increase hit count or hit bytes. It can still change DDR contention, issue timing, cross-core waits, and Makespan, as the two official results illustrate. A different cut or placement could change the transfer-key multiset and this bound; this audit makes no claim about that search space or the actual no-L2 CacheGain.

The next structural work for this fixed placement should target dependency and resource timing, especially reads whose first miss lies on the realized critical chain, rather than try to keep these already resident keys longer. This is a prioritization from the event evidence, not a new simulated result or a claim about which specific operation to move. If a new cut/placement is proposed for cache gain, first compare its distinct-key bytes and repeated-key bytes against this 1,012,064/11,264 baseline before spending an official evaluation call.

## Reproduction and provenance

Run `python3 results/a/q3-nikolastarx/prefix-cache-critical-audit-20260925/analyze_cache.py` from the repository root. Its captured output is `summary.json`. It reads two archived official results and frozen P3 source; it invokes no prepare, solver, or evaluator. The exact source SHA-256 values are in `summary.json`, including the archived prepared-evidence tarball (not opened by this script). The working HEAD during this audit was `e96a8551d6b3c92bbf00285376ce950f9246c0dc`. This audit did not alter the frozen plan or evaluation budget.
