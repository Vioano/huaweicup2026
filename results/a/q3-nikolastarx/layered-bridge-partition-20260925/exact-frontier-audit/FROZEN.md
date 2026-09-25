# Exact-frontier audit frozen before execution

Source commit `c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43`. Read-only inputs: official 005/086 graphs, the existing `partition.py` and corresponding JSON outputs, and the root `FRONTIER_LEMMA.md`. One Python script process, one worker, ≤60 seconds total wall alarm, one analysis per case (005 then 086), first exception stops, zero retries. Zero Task, Step, candidate construct, pipe_bound, E0/E1/E2 or other scoring calls. No new plan or owner is produced. Soft delegation budget: 3500 tokens and 10 minutes; actual token use unavailable.

Frozen SHA-256:

| File | SHA-256 |
| --- | --- |
| `audit.py` | `d9b6f4a483d9366a5a84567bd2b74c7f1260907103365a0b58edbb6f38c469bf` |
| parent `partition.py` | `2ba574437560e23edd50e69ce393d57a2294f50e6c544ae5840ec7c4dd99eb3b` |
| parent `005.json` | `ea0b246d108c2dc165dcabe7830395b9a148044ab12bb59a1a10dafeebb2c78c` |
| parent `086.json` | `ffaff44a66de6c2a643241c2df93a51a8fac1e70339a2785a1e11dbc05519f40` |
| parent `FRONTIER_LEMMA.md` | `45e98edda00d56ec9a716716e0bac6157320eae493fcb8473db08f5d809d6bbc` |
| official `case_005.json` | `c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f` |
| official `case_086.json` | `ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a` |
| official `stub_multicore_cut_and_schedule.py` | `0a3a3b79b5173b466fc05fc8d33b72d11d90b4df78995435853d91c632a35892` |

AST syntax review passed. The script reads each original graph's op DAG, groups each recognized row's full original op set as one quotient vertex, and leaves nonrow ops singleton for the first quotient. For the joint quotient it groups nonrow ops only if their **full row-ID upstream/downstream frontier sets** match, then takes weak components in the same-signature induced graph. It checks unique coverage of all original ops and exact original-pipe cycle sums. Each quotient is explicitly topologically audited. On a cycle it saves a finite cycle of quotient vertices plus original graph edge chains witnessing each arc; it does not silently treat a cycle as a valid construction. This checks the lemma's explicit acyclicity guard on these two graphs, not universal validity.
