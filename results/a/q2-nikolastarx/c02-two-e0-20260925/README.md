# C02 exit-sealed two-plan official probe

Both saved 069/K5 plans received one unmodified official P2 E0 evaluation, with no construction during this window, no E1/E2, no baseline call and no retry. Cold Python 3.12.13 on the shared Mac ARM64 host. This is saved-trace-assisted mechanism evidence, not a complete online solver or full500 benchmark.

| Plan | Makespan cycles | Change vs saved 11962 | Added DDR B | Spill B | External E0 wall s |
|---|---:|---:|---:|---:|---:|
| candidate 0, 48 operations | 12154 | +192 (+1.605%) | 338162 | 0 | 0.255219 |
| candidate 1, 45 operations | 11838 | -124 (-1.037%) | 335666 | 0 | 0.264704 |

Saved incumbent added DDR was 321938 B. Candidate 1 increases it by 13728 B (4.264%) while lowering M slightly. Both candidates are worse in M than the independently confirmed reverse proposal 10577, whose added DDR is 452436 B. This preserves the quality/DDR tradeoff; no combined score or new full500 mean is claimed.

The candidates removed three witnessed producer/receiver connections, passed structural and zero-spill checks, yet did not provide a large time improvement. Connection elimination and lower bounds do not imply a proportional Makespan reduction: entry copies and regional placement still matter. We stop expansion of these two C02 proposals and proceed with full500 qualification of the separate bidirectional algorithm. This does not disprove the exit-sealed invariant or all possible regional algorithms.

Provenance: fixed plans and full static construction evidence are in `../c02-real-static-20260925/`, published at f7e728e942a82788d61613c806232b27651e84fe; solver-provenance 15d plus recorded external-COPY_IN adapter patch. The runner here is a historical byte copy (e7a6ef9c); its original relative location was `output/c02-real-static-20260925/evaluate_two.py`, so do not directly execute the relocated archive copy. Its 90-second timer includes identity preflight. Raw graph/config and unmodified official code were verified before dispatch.

T0 2026-09-25T12:43:15Z: physical free 5497372672 B, memory_pressure free86%, disk232679243776 B, no conflicting scorer. The actual gate and private raw host receipt were preserved; the public host receipt omits unrelated raw process/system details and absolute interpreter path, with the original digest retained. Both children exited0, survivors empty, observer-inclusive maximum sampled RSS63668224 B. Parent and resource coordinator independently read back results and fresh release. All run originals, including trace/log and per-process receipts, are in the CRC-checked ZIP. No automatic additional C02 or full500 window is authorized by this result.
