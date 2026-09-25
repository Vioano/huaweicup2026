"""Fake-only coverage for failure after launching the remote runner."""

import importlib.util
import io
import json
import pathlib
import tarfile
from types import SimpleNamespace


SOURCE = (
    pathlib.Path(__file__).resolve().parents[2]
    / "results/a/p1-structural-two-cell-20260925/preflight/remote_setup.py"
)


def test_identity_acquisition_failure_kills_child_and_archives_evidence(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("p1_remote_setup_cleanup", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.BASE = tmp_path / "remote"
    module.BUNDLE = tmp_path / "source-bundle.tar.gz"
    module.WS = module.BASE / "workspace"
    module.EVID = module.BASE / "evidence"
    module.OUT = module.WS / "two-cell-run"
    manifest = {"files": [], "solver_commit": "3a1b82b71ca1ff6689eb8e72f17d26c48b52073c"}
    payload = (json.dumps(manifest) + "\n").encode()
    with tarfile.open(module.BUNDLE, "w:gz") as archive:
        info = tarfile.TarInfo("bundle-manifest.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    module.BUNDLE_SHA = module.sha(module.BUNDLE.read_bytes())

    events = []

    class FakeChild:
        pid = 43210
        dead = False

        def poll(self):
            return -9 if self.dead else None

        def kill(self):
            events.append("child.kill")
            self.dead = True

        def wait(self, timeout=None):
            events.append("child.wait")
            assert self.dead, "the launched child must be killed before reaping"
            return -9

    child = FakeChild()

    def fake_popen(*args, **kwargs):
        events.append("Popen")
        assert kwargs["start_new_session"] is True
        return child

    def fail_getpgid(pid):
        assert pid == child.pid
        events.append("getpgid")
        raise RuntimeError("injected identity lookup failure")

    def forbidden_killpg(*args):
        raise AssertionError("unverified process group must never be signalled")

    def fake_reap_adopted():
        events.append("reap_adopted")
        assert child.dead
        return {"confirmed": True, "observed": [], "remaining": []}

    monkeypatch.setattr(module.ctypes, "CDLL", lambda *a, **k: SimpleNamespace(prctl=lambda *a: 0))
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="fake uv"))
    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(module.os, "getpgid", fail_getpgid)
    monkeypatch.setattr(module.os, "killpg", forbidden_killpg)
    monkeypatch.setattr(module, "reap_adopted", fake_reap_adopted)

    module.main()

    assert events == ["Popen", "getpgid", "child.kill", "child.wait", "reap_adopted"]
    setup = json.loads((module.EVID / "setup.json").read_text())
    assert setup["status"] == "failed"
    assert "RuntimeError: injected identity lookup failure" in setup["error"]
    assert setup["runner_exited"] is True
    assert setup["adopted_cleanup"]["confirmed"] is True
    archive_path = module.BASE / "evidence.tar.gz"
    assert archive_path.is_file()
    with tarfile.open(archive_path, "r:gz") as archive:
        archived = json.loads(archive.extractfile("evidence/setup.json").read())
        assert archived["status"] == "failed"
        assert archived["error"] == setup["error"]
        assert "evidence/evidence-manifest.json" in archive.getnames()
