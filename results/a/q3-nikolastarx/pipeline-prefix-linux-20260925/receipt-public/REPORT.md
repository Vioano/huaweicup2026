# P3 044 Linux mechanism-cell export

This is one P3 044 / five-core official E0 result for frozen static plan `13914b24c18b59366be17de86a26d227ff85427cb00b184799587777547a6508` from solver/source commit `62c69b20ab887c76567dbab5fcce6eef30107b5c`. It is a mechanism cell, not a complete algorithm or full-suite score.

- Makespan: **38024 cycles**, versus the retained prior P3 result **38390** (0.9533732743% lower).
- Added data movement: **140800 B**; spill: **0 B**.
- P3 cache stats match the prior P3 result: hit bytes 11264, miss bytes 1012064, byte hit rate 0.0110072234904156. This does not establish CacheGain; the required same-plan P2 result is absent, so CacheGain remains unknown.
- Evaluation read/evaluate/write time: **1.952790842 s**, measured with tracing. It is external evaluation time, not solver time. Full plan-construction end-to-end wall time is unavailable, so solver wall is null.
- Calls: prepare phase Step1/Step2/Step3 = 5/5/5; P3 score phase Step1/Step2/prepare-Step3/step3-simulation = 5/5/5/5. Aggregate prepare-Step3 executions = 10; P3=1, P2=0, retries=0, unknown=0.
- Plan SHA: `13914b24c18b59366be17de86a26d227ff85427cb00b184799587777547a6508`; result SHA: `d4cdf8dbabe22923b9a74329741fb39e74a588e619d9f101db1fd28ecd629da1`; baseline SHA: `73f1d15fdea4f706b22099d2339a0e74a76c4114a68672077a98a8e15faa913c`; source archive SHA: `a923a07fc1ad549eecaae227e534d7a7de83ef1647a67a60a70d130c4aef8b05`.

## Evidence handling

`export.py` copies the frozen plan and baseline and safely reads only named regular members from the retained tar. The exact selected result and receipt bytes are kept under `raw-evidence/`; original `run-local` remains unchanged. Exact original receipts retain the local admission-document path as provenance; the derived `artifacts/run-public.json` omits it. Root reviewed the original archive and CLI outputs before publication; no credential material was found. No CLI credential or session connection fields are included in the feed.

The official result identity is scene B, problem 3, cache_mode read_only, five cores. Baseline is the unchanged official single-core scene A result. No P2 cache pair is claimed.
