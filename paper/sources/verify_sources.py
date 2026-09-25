"""Read-only integrity checks for this editorial import, not scientific validation.

Run from any cwd: python3 paper/sources/verify_sources.py
Requires local Git objects for the fixed source commits; never fetches or runs sources.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ERRORS: list[str] = []
WARNINGS: list[str] = []
CHECKED: set[str] = set()


def git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, check=False
    )


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_record(record: dict) -> bytes | None:
    source = record["commit"] + ":" + record["path"]
    result = git("show", source)
    if result.returncode:
        ERRORS.append("source Git object unavailable: " + source)
        return None
    if len(result.stdout) != record["bytes"] or sha256(result.stdout) != record["sha256"]:
        ERRORS.append("source bytes/hash mismatch: " + source)
    return result.stdout


def check_target(href: str, file: Path, inherited: bool = False) -> None:
    # This deliberately checks files/Git objects, not website availability or anchors.
    if href.startswith(("#", "mailto:")):
        return
    parsed = urlparse(href)
    spec: str | None = None
    if parsed.scheme:
        match = re.fullmatch(
            r"/huaweibei123/huaweicup2026/(?:blob|tree)/([0-9a-f]{40})(?:/(.*))?",
            unquote(parsed.path),
        )
        if parsed.netloc == "github.com" and match:
            commit, path = match.groups()
            spec = commit + (":" + path if path else "^{commit}")
    else:
        path = (file.parent / unquote(parsed.path)).resolve()
        if path.exists():
            return
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError:
            ERRORS.append(f"relative link escapes repository: {file.relative_to(ROOT)}: {href}")
            return
        spec = "HEAD:" + relative  # Sparse-checkout files may be absent on disk.
    if spec is None or spec in CHECKED:
        return
    CHECKED.add(spec)
    if git("cat-file", "-e", spec).returncode:
        message = f"unavailable link target: {file.relative_to(ROOT)}: {href}"
        (WARNINGS if inherited else ERRORS).append(message)


def main() -> int:
    manifest = json.loads((HERE / "manifest.json").read_text())
    for record in manifest["imports"]:
        original = verify_record(record)
        if original is None:
            continue
        mappings = {item["from"]: item["to"] for item in record["link_rewrites"]}

        def rewrite(match: re.Match[str]) -> str:
            old = match.group(1)
            return "](" + mappings.get(old, old) + ")"

        expected = re.sub(r"\]\(([^)\s]+)\)", rewrite, original.decode())
        copy = (ROOT / record["editorial_copy"]).read_text()
        marker = "<!-- source-body -->\n"
        if marker not in copy:
            ERRORS.append("source-body marker missing: " + record["editorial_copy"])
            continue
        actual = copy.split(marker, 1)[1]
        if actual != expected or sha256(actual.encode()) != record["imported_body_sha256"]:
            ERRORS.append("editorial body differs from recorded transformation: " + record["editorial_copy"])
    for record in manifest["fixed_documents"]:
        verify_record(record)
    chats = json.loads((HERE / "chat-entrypoints.json").read_text())
    for record in chats["entries"]:
        verify_record(record)
    files = [ROOT / "paper/README.md", ROOT / "tasks/paper/PAPER-PLANNING.md"]
    for directory in ["paper/chapters", "paper/planning", "paper/sources"]:
        files.extend(sorted((ROOT / directory).glob("*.md")))
    for file in files:
        text = file.read_text()
        body_at = text.find("<!-- source-body -->")
        # Ignore inline code and fenced blocks for link parsing.
        text = re.sub(r"```.*?```", lambda m: " " * len(m.group()), text, flags=re.S)
        text = re.sub(r"`[^`\n]+`", lambda m: " " * len(m.group()), text)
        definitions = dict(re.findall(r"^\[(?!\^)([^\]]+)\]:\s*(\S+)", text, re.M))
        for match in re.finditer(r"\]\(([^)\s]+)\)", text):
            check_target(match.group(1), file, body_at >= 0 and match.start() > body_at)
        for match in re.finditer(r"\]\[(?!\^)([^\]]+)\]", text):
            label = match.group(1)
            if label not in definitions:
                ERRORS.append(f"undefined reference: {file.relative_to(ROOT)}: {label}")
            else:
                check_target(definitions[label], file)
    print(json.dumps({
        "imports": len(manifest["imports"]),
        "fixed_documents": len(manifest["fixed_documents"]),
        "chat_entrypoints": len(chats["entries"]),
        "markdown_files": len(files),
        "git_link_targets_checked": len(CHECKED),
        "errors": ERRORS,
        "inherited_link_warnings": WARNINGS,
        "not_checked": ["scientific correctness", "web availability", "URL anchors", "local untracked PDFs on another checkout", "experiments", "LaTeX"],
    }, ensure_ascii=False, indent=2))
    return 1 if ERRORS else 0


if __name__ == "__main__":
    raise SystemExit(main())
