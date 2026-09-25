# One authorized recovery validation

The first failed targeted run and its frozen test source/logs remain in the parent directory. This is a separately authorized single recovery process, not a rewrite of that result. Before execution: guard `src/q3/layered_prepared_guard.py` SHA-256 `804e122433fb3e6e90d28d984c3204a8ca195364f32674511d679554c43ef5f2`; corrected test `tests/test_q3_multibucket_guard.py` SHA-256 `ad37d3dd1d31e390ea1cfb0ca7c20743613a8de55cd80d9a33e51bf5edebab4a`; `verify.py` SHA-256 `d61ed090b5d58648787fd11afcea74217058b8ae2fc5713fb427ff600d722494`. HEAD `03f594598259a8ad2162e8247d5a9c659c57c133`.

Archived inputs: raw graph `c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f`; old plan `2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a`; prepared `91c9e4ff2995d091922f7ae1b0975de98174a9487a1d0458a05c60535beb5c44`. The runner checks them before pure guard readback. It runs exactly five corrected synthetic unittest cases, then default and allow_multi guard on the same archived *singleton* R9 plan. No 194-op Task exists and none is claimed verified. One Python child, 30 s total timeout, first exception stops, zero retries, zero official Task/Step/E0/E1/E2 calls. Command executed by the supervisor below:

```sh
python3 -B results/a/q3-nikolastarx/multibucket-guard-20260925/recovery/verify.py
```
