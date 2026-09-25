"""Run only after coordinator admission; one CLI allocation, no retries."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import zipfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("package", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--package-sha256", required=True)
    p.add_argument("--admission-ref", required=True)
    p.add_argument("--cli", type=Path, required=True)
    a = p.parse_args()
    if hashlib.sha256(a.package.read_bytes()).hexdigest() != a.package_sha256:
        raise RuntimeError("package identity differs")
    job = Path(__file__).with_name("q3_partial_colab_job.py")
    with zipfile.ZipFile(a.package) as bundle:
        package = json.loads(bundle.read('package.json'))
    if hashlib.sha256(job.read_bytes()).hexdigest() != package['job_sha256']:
        raise RuntimeError('remote job identity differs from transport manifest')
    session = "q3-partial-044-20260925"
    a.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    record = {"session": session, "admission_reference": a.admission_ref,
              "package_sha256": a.package_sha256, "attempts": [], "status": "starting",
              "allocation_attempted": False}

    def call(label, args, cap):
        remaining = 600 - (time.monotonic() - started)
        # Cleanup receives its own bounded time even after a failed execution.
        timeout = cap if label in {"download", "stop", "sessions-after"} else min(cap, remaining)
        if timeout <= 0:
            raise TimeoutError("local total allocation window exceeded")
        with (a.output / (label + ".stdout.txt")).open("xb") as out, (a.output / (label + ".stderr.txt")).open("xb") as err:
            try:
                result = subprocess.run([str(a.cli), "--auth", "oauth2", *args],
                                        stdout=out, stderr=err, timeout=timeout)
                entry = {"label": label, "exit_code": result.returncode}
            except subprocess.TimeoutExpired:
                entry = {"label": label, "timeout": timeout}
        record["attempts"].append(entry)
        (a.output / "control.json").write_text(json.dumps(record, indent=2) + "\n")
        if entry.get("exit_code") != 0:
            raise RuntimeError(label + " did not complete successfully")

    bootstrap = a.output / "bootstrap.py"
    bootstrap.write_text("import runpy\njob=runpy.run_path('/content/q3_partial_colab_job.py')\n"
                         + "job['run']('/content/q3-partial-package.zip', "
                         + repr(a.package_sha256) + ", " + repr(a.admission_ref) + ")\n")
    try:
        # The coordinator's fresh no-conflict snapshot is a prerequisite. No
        # implicit allocation by exec and no attempt to reuse another session.
        call("sessions-before", ["sessions"], 10)
        before = ((a.output / 'sessions-before.stdout.txt').read_text()
                  + (a.output / 'sessions-before.stderr.txt').read_text()).lower()
        if 'no active sessions' not in before:
            raise RuntimeError('fresh Colab conflict check did not report empty sessions')
        record['allocation_attempted'] = True
        call("new", ["new", "--session", session], 60)
        call("upload-package", ["upload", str(a.package.resolve()), "/content/q3-partial-package.zip", "--session", session], 30)
        call("upload-job", ["upload", str(job.resolve()), "/content/q3_partial_colab_job.py", "--session", session], 30)
        call("execute", ["exec", "--session", session, "--file", str(bootstrap.resolve()), "--timeout", "545"], 555)
        record["status"] = "remote_command_completed"
    except BaseException as error:
        record.update(status="failed", error=type(error).__name__ + ": " + str(error))
    finally:
        for label, args, cap in [
            ("download", ["download", "/content/q3-partial-817e-evidence.tar.gz", str((a.output / "evidence.tar.gz").resolve()), "--session", session], 20),
            ("stop", ["stop", "--session", session], 25),
            ("sessions-after", ["sessions"], 10),
        ]:
            if not record['allocation_attempted']:
                break
            try:
                call(label, args, cap)
            except BaseException as error:
                record[label + "_error"] = type(error).__name__ + ": " + str(error)
        record["wall_seconds"] = time.monotonic() - started
        record["stop_confirmation"] = "Inspect stop and sessions-after readback; exit code alone is not VM stop proof"
        (a.output / "control.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
