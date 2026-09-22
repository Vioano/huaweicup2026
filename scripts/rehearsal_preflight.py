"""Read-only readiness check. Never creates identities, issues or branches."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = "huaweibei123/huaweicup2026"


def main() -> int:
    report = {"scope": "read-only; not a live rehearsal result", "checks": {}}
    errors = []

    def run(name, args, parse=False):
        try:
            result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                                    encoding="utf-8", timeout=45, check=True)
            value = json.loads(result.stdout) if parse else result.stdout.strip()
            report["checks"][name] = value
            return value
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            # Do not dump authentication/transport stderr into a shareable report.
            errors.append(f"{name}: {type(exc).__name__}; inspect this command locally")
            return None

    run("git", ["git", "--version"])
    node = run("node", ["node", "--version"])
    if node and int(node.removeprefix("v").split(".")[0]) < 22:
        errors.append("Use Node.js 22+ for the project rehearsal")
    node_platform = run("node_platform", ["node", "-p", "process.platform"])
    if node_platform == "win32":
        errors.append("Atlas 0.5.0 native Windows is blocked by directory fsync EPERM; use Linux/WSL2 (see rehearsal docs)")
    run("gh", ["gh", "--version"])
    run("commit", ["git", "rev-parse", "HEAD"])
    origin = run("origin", ["git", "remote", "get-url", "origin"])
    if origin not in (f"https://github.com/{REPO}.git", f"https://github.com/{REPO}",
                      f"git@github.com:{REPO}.git", f"ssh://git@github.com/{REPO}.git"):
        errors.append("origin must be the shared team repository")
    run("worktree", ["git", "status", "--short"])
    run("actor", ["gh", "api", "user", "--jq", ".login"])
    permissions = run("permissions", ["gh", "api", f"repos/{REPO}",
                                      "--jq", ".permissions"], parse=True)
    if permissions and not permissions.get("push"):
        errors.append("GitHub account lacks repository push permission")
    run("remote_read", ["git", "ls-remote", "--exit-code", "origin", "refs/heads/main"])
    for name in ("system-atlas", "scientific-figure-making"):
        manifest = json.loads((ROOT / "docs" / f"{name}-install.json").read_text())
        mismatched = []
        for item in manifest["files"]:
            path = ROOT / manifest["install_path"] / item["path"]
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                mismatched.append(item["path"])
        report["checks"][name] = {"commit": manifest["commit"], "mismatched": mismatched}
        if mismatched:
            errors.append(f"{name}: files differ from installation manifest")
    run("model", ["node", str(ROOT / ".agents/skills/system-atlas/bin/system-atlas.mjs"),
                  "validate", "tests/rehearsal/system.json", "--repo-root", ".", "--json"], parse=True)
    report.update(ok=not errors, errors=errors)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
