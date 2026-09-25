# P2 shared stationary pipeline: 044/K5 Colab capsule

This is the frozen one-cell qualification package. Its complete official outcome is in [RESULTS.md](RESULTS.md). The earlier [stage-major negative result](../shared-stationary-044-pilot-20260926/RESULTS.md) motivated job-major ordering.

At packaging time, local `pack.py` performed a hash-only preflight and wrote `capsule.zip`; that step ran no constructor, E0, E1 or E2. The job-major source is fixed at `cbad84f726fecd997eeb76f3735ce5a2269225cb`. Old c665 official 044/K5 is Makespan 43795 and added COPY bytes 930400. This one-cell pilot is a mechanism test, not a full500 score or an online selector.

Static checks on 044/K5 give stage bounds `[0,17,24,28,39,51]`, external L1 input bytes `[77536,313344,294912,255488,11648]`, and a two-job produced-tensor reserve of 198144 B per core against 524288 B L1 capacity. A first-job cross-core producer on core 0 moves from rank 189/220 in the earlier stage-major plan to rank 38/429 here; this is only a priority-order observation. The new no-spill transfer estimate is 129536 B of crossing COPY out plus in, and official Step2 may differ. The strict recognizer plus capacity screen accepts only 3 of 100 official graphs at K5 (004, 044, 093), so even a 044 win would require a broader rule before claiming a material full-set improvement.

`pack.py` requires that the fixed solver source commit is an ancestor of HEAD and that all six included solver modules are byte-for-byte identical to that commit. It checks the graph/config against both c665 completed-row hashes and the official source manifest, and checks every official Python source against that manifest. The capsule contains the required six solver modules, all ten official Python modules, graph, config, runner and SHA-256 manifest. The runner verifies every payload hash before any construction. It performs exactly one cold `shared_stationary_pipeline.build` and one separate unmodified official P2 E0, saving complete plan, detail, construction receipt, official result, trace, log, stdout/stderr and process receipts. Its limits are one worker, construction ≤30 s, E0 ≤60 s, total ≤120 s, observed process-tree RSS ≤2 GiB, zero retries. Any failure stops the batch. Output lives outside the extracted capsule.

Local preflight: `python3 -B results/a/q2-nikolastarx/shared-stationary-pipeline-044-pilot-20260926/pack.py --official-data-root <frozen-official-data-directory>`. This only reads and hashes code/data, then writes the ZIP, manifest and preflight JSON in this directory. Use the recorded ZIP and manifest SHA-256 values in `preflight.json`; the pinned values for this package are below. Repacking is byte-reproducible when the source and runner bytes are unchanged; check `preflight.json` again before upload.

For later coordinator review, upload `capsule.zip` as `/content/p2-shared-stationary-pipeline-044.zip` to a standard Colab CPU Python runtime with `ps` available. No package install, Git checkout, native E2 or high-memory/GPU runtime is required. Run **this single cell once**; it validates the uploaded ZIP, extracts safely, runs the capsule once, retains failure artifacts and creates `/content/p2-shared-stationary-pipeline-044-results.zip` for download. The cell itself has not been executed here.

```python
from pathlib import Path
import hashlib, json, platform, sys, time, zipfile
archive = Path('/content/p2-shared-stationary-pipeline-044.zip')
expected = '89ca3a845d3381881ec7fd076655b74cb87f066a76efbc1445cdbe3ba070a43b'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
root = Path('/content/p2-shared-stationary-pipeline-044').resolve()
root.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        assert (root / name).resolve().is_relative_to(root)
    assert z.testzip() is None
    z.extractall(root)
output = Path('/content/p2-shared-stationary-pipeline-044-output')
command = [sys.executable, '-B', str(root / 'results/a/q2-nikolastarx/shared-stationary-pipeline-044-pilot-20260926/runner.py'), '--output', str(output)]
sys.path.insert(0, str(root))
from src.q2_nikolastarx.evaluate_feedback import monitored
launcher_process = Path('/content/p2-shared-stationary-pipeline-044-launcher-process')
started = time.perf_counter()
try:
    outer = monitored(command, launcher_process, time.perf_counter() + 130, 2 << 30)
    completion = {'status': outer['status'], 'returncode': outer['exit_code'],
                  'surviving_pids': outer['surviving_pids'],
                  'launcher_wall_seconds': time.perf_counter() - started,
                  'python': sys.version, 'platform': platform.platform(),
                  'capsule_sha256': expected}
except BaseException as error:
    completion = {'status': 'launcher_error', 'error': repr(error),
                  'launcher_wall_seconds': time.perf_counter() - started,
                  'capsule_sha256': expected}
(Path('/content/p2-shared-stationary-pipeline-044-completion.json')).write_text(json.dumps(completion, indent=2) + '\n')
result_zip = Path('/content/p2-shared-stationary-pipeline-044-results.zip')
with zipfile.ZipFile(result_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for folder, prefix in ((output, 'output'), (launcher_process, 'launcher-process')):
        if folder.exists():
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    z.write(path, prefix + '/' + str(path.relative_to(folder)))
    z.write('/content/p2-shared-stationary-pipeline-044-completion.json', 'completion.json')
    z.write(root / 'capsule-manifest.json', 'capsule-manifest.json')
print(json.dumps(completion))
print('result_zip_sha256:', hashlib.sha256(result_zip.read_bytes()).hexdigest())
print('result_zip_bytes:', result_zip.stat().st_size)
if completion.get('status') != 'ok' or completion.get('surviving_pids'):
    raise RuntimeError('pilot stopped; download results ZIP and inspect, do not retry')
```

Download the result ZIP and preserve its SHA-256. Compare the independent E0 `result.json` with the old 43795/930400 B only after checking `receipt.json`, both process receipts, plan hash and the complete trace/log. Colab host timing is a separate measurement from the old Mac batch; allocation, transfer and download times are outside the runner receipt.
