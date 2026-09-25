# P2 shared stationary wave: 044/K5 Colab capsule

Prepared only. Local `pack.py` performed a hash-only preflight and wrote `capsule.zip`; no constructor, E0, E1 or E2 ran. The source is fixed at `65b70e29e96115c1e365493a89f1e8a44339bc25`. Old c665 official 044/K5 is Makespan 43795 and added COPY bytes 930400. This one-cell pilot is a mechanism test, not a full500 score or an online selector.

`pack.py` requires that the fixed solver source commit is an ancestor of HEAD and that all five included solver modules are byte-for-byte identical to that commit. It checks the graph/config against both c665 completed-row hashes and the official source manifest, and checks every official Python source against that manifest. The capsule contains the required five solver modules, all ten official Python modules, graph, config, runner and SHA-256 manifest. The runner verifies every payload hash before any construction. It performs exactly one cold `shared_stationary_wave.build` and one separate unmodified official P2 E0, saving complete plan, detail, construction receipt, official result, trace, log, stdout/stderr and process receipts. Its limits are one worker, construction ≤30 s, E0 ≤60 s, total ≤120 s, observed process-tree RSS ≤2 GiB, zero retries. Any failure stops the batch. Output lives outside the extracted capsule.

Local preflight: `python3 -B results/a/q2-nikolastarx/shared-stationary-044-pilot-20260926/pack.py --official-data-root <frozen-official-data-directory>`. This only reads and hashes code/data, then writes the ZIP, manifest and preflight JSON in this directory. Use the recorded ZIP and manifest SHA-256 values in `preflight.json`; the pinned values for this package are below. Repacking is byte-reproducible when the source and runner bytes are unchanged; check `preflight.json` again before upload.

For later coordinator review, upload `capsule.zip` as `/content/p2-shared-stationary-044.zip` to a standard Colab CPU Python runtime with `ps` available. No package install, Git checkout, native E2 or high-memory/GPU runtime is required. Run **this single cell once**; it validates the uploaded ZIP, extracts safely, runs the capsule once, retains failure artifacts and creates `/content/p2-shared-stationary-044-results.zip` for download. The cell itself has not been executed here.

```python
from pathlib import Path
import hashlib, json, platform, sys, time, zipfile
archive = Path('/content/p2-shared-stationary-044.zip')
expected = 'b62c1db041cfd2e986e2c877ac0c69b5b9584fef326385f6de5182034312865b'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
root = Path('/content/p2-shared-stationary-044').resolve()
root.mkdir(exist_ok=False)
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        assert (root / name).resolve().is_relative_to(root)
    assert z.testzip() is None
    z.extractall(root)
output = Path('/content/p2-shared-stationary-044-output')
command = [sys.executable, '-B', str(root / 'results/a/q2-nikolastarx/shared-stationary-044-pilot-20260926/runner.py'), '--output', str(output)]
sys.path.insert(0, str(root))
from src.q2_nikolastarx.evaluate_feedback import monitored
launcher_process = Path('/content/p2-shared-stationary-044-launcher-process')
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
(Path('/content/p2-shared-stationary-044-completion.json')).write_text(json.dumps(completion, indent=2) + '\n')
result_zip = Path('/content/p2-shared-stationary-044-results.zip')
with zipfile.ZipFile(result_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for folder, prefix in ((output, 'output'), (launcher_process, 'launcher-process')):
        if folder.exists():
            for path in sorted(folder.rglob('*')):
                if path.is_file():
                    z.write(path, prefix + '/' + str(path.relative_to(folder)))
    z.write('/content/p2-shared-stationary-044-completion.json', 'completion.json')
    z.write(root / 'capsule-manifest.json', 'capsule-manifest.json')
print(json.dumps(completion))
print('result_zip_sha256:', hashlib.sha256(result_zip.read_bytes()).hexdigest())
print('result_zip_bytes:', result_zip.stat().st_size)
if completion.get('status') != 'ok' or completion.get('surviving_pids'):
    raise RuntimeError('pilot stopped; download results ZIP and inspect, do not retry')
```

Download the result ZIP and preserve its SHA-256. Compare the independent E0 `result.json` with the old 43795/930400 B only after checking `receipt.json`, both process receipts, plan hash and the complete trace/log. Colab host timing is a separate measurement from the old Mac batch; allocation, transfer and download times are outside the runner receipt.
