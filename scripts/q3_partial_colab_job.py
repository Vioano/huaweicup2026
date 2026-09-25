"""Remote setup/collection for a separately admitted, frozen CPU-only diagnostic.

Upload this file and the fixed ZIP; call run() from the Colab kernel. This file
does not allocate a VM. The local controller must download evidence and stop its
own Colab session in a finally block, including setup and observation failures.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import zipfile

SOURCE = "817e9e399f5efaf66cea6ddc495fe444950e43f2"
MANIFEST_SHA = "b36ef3ae7b974b139d9f7d5969a27df7868ebfba9d69818d26055bc83bd310a4"
BASE = Path("/content/q3-partial-817e-20260925")
ARCHIVE = Path("/content/q3-partial-817e-evidence.tar.gz")
SOURCE_URL = "https://github.com/huaweibei123/huaweicup2026.git"
STATIC = "results/a/q3-nikolastarx/pipeline-prefix-static-20260925"
PROBE = "results/a/q3-nikolastarx/partial-preload-one-20260925"
MEMBERS = {"package.json", "case_044.json", "manifest.json"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(bundle, bundle_sha256, admission_ref):
    if platform.system() != "Linux" or not admission_ref.strip():
        raise RuntimeError("Linux and explicit resource-admission reference required")
    if len(bundle_sha256) != 64 or sha(bundle) != bundle_sha256:
        raise RuntimeError("transport identity differs")
    BASE.mkdir(exist_ok=False)  # No silent restart after setup or scoring failure.
    started = time.monotonic()
    receipt = {"started_at": datetime.now(timezone.utc).isoformat(),
               "source_commit": SOURCE, "bundle_sha256": bundle_sha256,
               "admission_reference": admission_ref, "status": "setup",
               "kernel_python": platform.python_version(), "host": platform.platform(),
               "environment_recipe": "CPU Standard; uv==0.11.15; CPython3.12.13; uv sync --locked",
               "host_image": "Colab managed image observed, not a pinned Docker image",
               "max_setup_seconds": 150, "max_probe_seconds": 380, "max_driver_seconds": 540,
               "setup_commands": [], "supervisor_started": False}

    def save():
        (BASE / "remote-driver.json").write_text(json.dumps(receipt, indent=2) + "\n")

    def command(argv, cwd, limit, label):
        remaining = (150 if not receipt["supervisor_started"] else 530) - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("driver deadline before " + label)
        timeout = min(limit, remaining)
        with (BASE / (label + ".stdout.txt")).open("xb") as out, (BASE / (label + ".stderr.txt")).open("xb") as err:
            child = subprocess.Popen(argv, cwd=cwd, stdout=out, stderr=err, start_new_session=True,
                                     env={**os.environ, "UV_PYTHON_DOWNLOADS": "automatic", "PYTHONUTF8": "1"})
            try:
                rc = child.wait(timeout=timeout)
            except BaseException:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=5)
                raise
        receipt["setup_commands"].append({"label": label, "argv": argv, "exit_code": rc})
        save()
        if rc:
            raise RuntimeError(label + " failed: " + str(rc))

    save()
    repo = BASE / "source"
    try:
        with zipfile.ZipFile(bundle) as z:
            if len(z.namelist()) != len(MEMBERS) or set(z.namelist()) != MEMBERS:
                raise RuntimeError("unexpected ZIP members")
            if sum(i.file_size for i in z.infolist()) > 2_000_000:
                raise RuntimeError("unexpected expanded transport size")
            for name in sorted(MEMBERS):
                (BASE / name).write_bytes(z.read(name))
        package = json.loads((BASE / "package.json").read_text())
        if package["source_commit"] != SOURCE:
            raise RuntimeError("package source differs")
        for name in MEMBERS - {"package.json"}:
            if sha(BASE / name) != package["sha256"][name]:
                raise RuntimeError("package member differs: " + name)
        if sha(BASE / "manifest.json") != MANIFEST_SHA:
            raise RuntimeError("original manifest changed")
        repo.mkdir()
        command(["git", "init", "-q"], repo, 10, "git-init")
        command(["git", "remote", "add", "origin", SOURCE_URL], repo, 10, "git-remote")
        command(["git", "-c", "protocol.version=2", "fetch", "--depth=1", "--filter=blob:none", "origin", SOURCE], repo, 60, "git-fetch")
        command(["git", "sparse-checkout", "set", "--no-cone", "/src/q3/", "/data/raw/a/official/code/",
                 "/data/raw/a/official/data/config.txt", "/docs/a/source-manifest.json", "/uv.lock", "/pyproject.toml",
                 "/README.md", "/" + STATIC + "/", "/" + PROBE + "/",
                 "/scripts/q3_prefix_linux_supervisor.py",
                 "/results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/run-local/evidence.tar.gz"], repo, 10, "git-sparse")
        command(["git", "checkout", "--detach", SOURCE], repo, 60, "git-checkout")
        shutil.copyfile(BASE / "case_044.json", repo / "data/raw/a/official/data/case_044.json")
        if sha(repo / PROBE / "manifest.json") != MANIFEST_SHA:
            raise RuntimeError("tracked candidate manifest differs")
        command([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "uv==0.11.15"], BASE, 60, "install-uv")
        command([sys.executable, "-m", "uv", "sync", "--locked", "--python", "3.12.13"], repo, 100, "uv-sync")
        python = repo / ".venv/bin/python"
        receipt["python_binary_sha256"] = sha(python.resolve())
        receipt["uv_lock_sha256"] = sha(repo / "uv.lock")
        receipt["supervisor_sha256"] = sha(repo / "src/q3/partial_preload_probe.py")
        receipt["status"] = "probe"
        receipt["supervisor_started"] = True
        save()
        command([str(python), "-B", "-m", "src.q3.partial_preload_probe",
                 str(repo / PROBE), str(repo / PROBE / "run-linux"), "--source", SOURCE,
                 "--manifest-sha256", MANIFEST_SHA, "--admission-ref", admission_ref], repo, 380, "probe")
        result = json.loads((repo / PROBE / "run-linux/run.json").read_text())
        if result.get("status") != "complete":
            raise RuntimeError("supervisor did not report a complete probe")
        receipt["probe_summary"] = {k: result.get(k) for k in ["candidate_M", "control_M", "candidate_G", "control_G"]}
        receipt["status"] = "complete"
    except BaseException as error:
        receipt["status"] = "failed"
        receipt["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        receipt["driver_wall_seconds"] = time.monotonic() - started
        save()
        with tarfile.open(ARCHIVE, "x:gz") as archive:
            for path in sorted(BASE.glob("*.json")) + sorted(BASE.glob("*.txt")):
                archive.add(path, arcname="driver/" + path.name)
            output = repo / PROBE / "run-linux"
            if output.exists():
                archive.add(output, arcname="probe")
            preflight = repo / PROBE / "run-linux.preflight.json"
            if preflight.exists():
                archive.add(preflight, arcname="driver/probe-preflight.json")
        print(json.dumps({"status": receipt["status"], "evidence_path": str(ARCHIVE),
                          "evidence_sha256": sha(ARCHIVE), "supervisor_started": receipt["supervisor_started"]}))
