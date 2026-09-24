# Static mandatory COPY diagnosis

Pilot `a6b09dcebf26c5ac28bcb4378dec8dbf06b0c075`; manifest SHA-256 `7af8890338b120e6b179fe96fbaacf746b2ab7ad34a1f2dabe2945afdd29f597`. Only four already selected plans/results were analyzed. No solver/E0/E1/E2 ran.

`mandatory_copy_work` counts boundary input/output, cross-tensor and cross-direct original COPYs before Step2 spill. `service_work` sums per-COPY max(1, ceil(size / 60)); it is an abstract service-work measure, **not an exact official makespan lower bound**. The original prose omitted max(1); stored counts already came from the correct API. `diagnosis.json` was not modified. The separate per-tensor accounting counts each cross-core tensor pair as one OUT plus one IN.

| Cell | Selected | Old→new scheduled bytes | Added DDR Δ | COPY bytes old→new by category (BI / BO / tensor / direct) | Work old→new (same order) | zero-spill exact match? |
|---|---|---:|---:|---|---|---|
| 003/k2 | candidate_selected | 1382568→6351422 | 4968854 | 1382534/34/0/0 → 1708300/34/4643088/0 | 23189/17/0/0 → 28657/17/81822/0 | True/True |
| 005/k3 | candidate_selected | 3434800→2727442 | -707358 | 560176/14592/2860032/0 → 623922/14592/2088928/0 | 9425/247/49464/0 → 10495/247/36108/0 | True/True |
| 056/k5 | candidate_selected | 221600→5084836 | 4863236 | 221526/74/0/0 → 467954/74/4616808/0 | 3835/37/0/0 → 8086/37/81656/0 | True/True |
| 008/k5 | baseline_retained | 2654424→2654424 | 0 | 1990872/663552/0/0 → 1990872/663552/0/0 | 33480/11124/0/0 → 33480/11124/0/0 | True/True |

## Interpretation

003/k2 adds 4,968,854 scheduled bytes: boundary input +325,766, cross-tensor +4,643,088; boundary output and direct edges are unchanged/zero. This is spread across 3,544 tensors and 3,544 core-pair cuts; the ten largest account for 1.8% of positive cross-tensor growth.
056/k5 adds 4,863,236 bytes: boundary input +246,428, cross-tensor +4,616,808; output/direct unchanged/zero. Growth spans 2,309 tensors and 3,000 core-pair cuts; top ten are 1.8% of growth. Thus neither case's DDR increase is concentrated in a few tensors; many split tensors could be co-location candidates, but no specific merge is certified to preserve Makespan, legality, or spill behavior.

Per-cell tensor-pair contributions are in `diagnosis.json`; top-ten entries include tensor IDs and source/destination cores. This is structural diagnosis, not causal proof about observed Makespan.

## Source limits

Inputs and SHA checks are recorded in `diagnosis.json`; baseline plan/truth bytes come from the manifest-pinned Git commit and graph/selected archives from the pilot commit. No graph or source files were changed. No scheduleStep or lower-bound API was run.

## Hyperedge identity check

`hypergraph-check.json` independently recounts all eight pinned old/new plans by input, output, cross-tensor, and direct-edge hyperedges; every category and total equals `mandatory_copy_work.transfer_bytes`, and every zero-spill total equals E0 `scheduled_copy_bytes`. A fixed-seed 2,000-case synthetic pin test checked 6,889 incident-edge move deltas against brute-force core-set costs with zero mismatches. Producer pins are included; direct edges are two-pin edges. Same-core reorder leaves this original pre-Step2 COPY byte count invariant, but gives no Makespan guarantee.
