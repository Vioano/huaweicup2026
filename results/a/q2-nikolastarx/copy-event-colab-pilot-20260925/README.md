# Fixed-owner COPY-event Colab ablation

The same three official graphs 005/009/015 at five cores use their frozen c665 selected plans as controlled seeds. Only eligible execution order changes; original owner and singleton mapping are asserted equal. This is a mechanism ablation, not a cold full solver, a historical best-combination score, or a new full500 result. A production algorithm would have to generate/select the seed online and include all those costs.

Source: copy_event_retime at 978b6f4c86a5c7057f1bc2f98abaed7fdaac2f53. One standard Colab CPU worker; at most three constructions and three official E0 calls, zero E2/retries; 60 seconds per stage, 360 seconds per batch, 4 GiB observed process-tree RSS. New session/capsule/output; no resuming the previous latency pilot. Every source/input/seed byte is checked against the capsule manifest before construction, and seed graph/plan/result identity was checked against the completed c665 audit when packaging.

Only synthetic tests have run at this preparation commit. Real output will be added separately, including failures.
