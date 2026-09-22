"""Exercise rehearsal CLI commands against a disposable LOCAL bare Git remote.

No gh calls, GitHub writes, real identities, UI interaction or remote Agents.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / ".agents/skills/system-atlas/bin/system-atlas.mjs"


def main():
    with tempfile.TemporaryDirectory(prefix="huaweicup-cli-rehearsal-") as tmp:
        root = Path(tmp)
        leader, member, remote = (root / name for name in ("leader", "member", "remote.git"))
        subprocess.run(["git", "init", "--bare", "--quiet", str(remote)], check=True)

        def cli(*args):
            p = subprocess.run(["node", str(CLI), *map(str, args)], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", timeout=90)
            if p.returncode:
                raise RuntimeError(p.stderr or p.stdout)
            return json.loads(p.stdout)

        def payload(name, value):
            path = root / (name + ".json")
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            return path

        def state(who):
            return cli("team", "state", "--state", who)

        invite = cli("team", "init-leader", "--state", leader, "--model", ROOT / "tests/rehearsal/system.json",
                     "--repo-root", ROOT, "--project", "local-rehearsal", "--actor", "leader",
                     "--remote", remote, "--branch", "atlas-rehearsal/local")
        identity = cli("team", "init-member", "--state", member, "--actor", "member",
                       "--invite", payload("invite", invite))
        with (root / "serve.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(["node", str(CLI), "team", "serve", "--state", str(leader),
                                        "--interval", "3600"], stdout=log, stderr=log, cwd=ROOT)
            try:
                for _ in range(150):
                    if process.poll() is not None:
                        raise RuntimeError((root / "serve.log").read_text())
                    if '"url"' in (root / "serve.log").read_text():
                        break
                    time.sleep(0.2)
                else:
                    raise RuntimeError("Leader did not start in 30 seconds")

                task = {"id": "check-member", "title": "本地机制预演", "description": "非真机联测",
                        "status": "todo", "assignees": ["member"], "entities": ["analysis"],
                        "acceptance": ["Read back signed accepted state"], "deliverables": [], "blocked": ""}
                cli("task", leader / "model.json", "--payload", payload("create", {
                    "operationId": "local-create", "expectedCursor": state(leader)["cursor"],
                    "action": "create", "task": task}))
                cli("team", "grant", "--state", leader, "--payload", payload("grant", {
                    **identity, "grants": [{"nodes": ["analysis"], "fields": ["inputs"], "comments": True}],
                    "taskGrants": [{"tasks": [task["id"]], "fields": ["status", "blocked", "deliverables"]}]}))

                def sync():
                    for who in (leader, member, leader, member):
                        cli("team", "sync", "--state", who)

                sync()

                def change(field, value, version=None):
                    return {"operation": "task.set", "taskId": task["id"], "field": field, "value": value,
                            "expectedVersion": state(member)["fieldVersions"][f"task:{task['id']}:{field}"]
                            if version is None else version}

                def request(name, changes, expected):
                    cli("team", "request", "--state", member, "--payload",
                        payload(name, {"requestId": name, "changes": changes}))
                    sync()
                    receipt = next(item["receipt"] for item in state(member)["outbox"] if item["requestId"] == name)
                    assert receipt and (receipt.get("code") or receipt["status"]) == expected, receipt
                    return receipt

                version = state(member)["fieldVersions"]["task:check-member:status"]
                request("local-doing", [change("status", "doing")], "accepted")
                request("local-stale", [change("status", "review", version)], "team/conflict")
                request("local-denied", [change("blocked", "MUST-NOT-APPLY"), change("assignees", ["leader"])], "team/forbidden")
                request("local-review", [change("status", "review")], "accepted")
                boards = [cli("team", "query", "--state", who, "--mode", "board", "--detail", "full") for who in (leader, member)]
                assert boards[0]["cursor"] == boards[1]["cursor"]
                assert boards[0]["records"] == boards[1]["records"]
                assert boards[0]["complete"] and not boards[0]["page"]["hasMore"]
                accepted_task = boards[0]["records"][0]["value"]
                assert accepted_task["status"] == "review" and accepted_task["blocked"] == ""
                print(json.dumps({"ok": True, "scope": "local CLI + disposable bare Git only",
                                  "checks": ["leader task creation", "grant", "signed accepted request", "stale conflict",
                                             "atomic permission rejection", "same-cursor board readback"],
                                  "live_multi_machine": "NOT TESTED", "human_viewer": "NOT TESTED"}, indent=2))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
