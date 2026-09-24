"""Export a consistent compact central view without copying original artifacts."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from contextlib import closing

MAX_COMPRESSED = 32 * 1024 * 1024
MAX_DECODED = 256 * 1024 * 1024


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def git_json(repo, commit, path):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("A fixed website commit is required")
    data = subprocess.check_output(["git", "-C", str(repo), "show", commit + ":" + path])
    return json.loads(data)


def read_central(db_path, *, frozen_manifest, algorithms, code_commit):
    # Read-only URI avoids creating an empty authority when the path is wrong.
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Central history failed SQLite integrity check; publication stopped")
        records = []
        for sequence, record_id, body in db.execute("SELECT seq,id,body FROM records ORDER BY seq"):
            record = json.loads(body)
            if record.get("id") != record_id:
                raise ValueError("Central record ID mismatch")
            records.append(dict(record, sequence=sequence))
        sources = {name: json.loads(body) for name, body in db.execute("SELECT id,body FROM sources")}
        cursor = db.execute("SELECT COALESCE(MAX(seq),0) FROM events").fetchone()[0]
        event_ids = {json.loads(body)["id"] for (body,) in db.execute("SELECT body FROM events WHERE kind='record'")}
        if event_ids != {r["id"] for r in records}:
            raise ValueError("Central event/history mismatch; publication stopped")
    payload = {
        "schema_version": 1,
        "generated_at": now(),
        "central_url": "https://github.com/huaweibei123/huaweicup2026",
        "sequence": cursor,
        "records": records,
        "source_status": sources,
        "manifest": frozen_manifest,
        "algorithms": algorithms,
        "publisher": {
            "actor": "nikolastarx",
            "role": "central-benchmark-board",
            "board_code_commit": code_commit,
            "verification_scope": "Central admission results; this is not member-side re-evaluation.",
        },
    }
    validate_payload(payload)
    payload["record_count"] = len(records)
    payload["record_ids_sha256"] = digest(("\n".join(sorted(r["id"] for r in records)) + "\n").encode())
    payload["records_sha256"] = digest(canonical(records))
    semantic_sources = {name: {k: v for k, v in state.items() if k not in ("checked_at", "started_at")}
                        for name, state in sources.items()}
    payload["snapshot_id"] = digest(canonical({
        "sequence": cursor, "records_sha256": payload["records_sha256"],
        "sources": semantic_sources, "manifest": frozen_manifest,
        "algorithms": algorithms, "publisher": payload["publisher"],
    }))
    return payload


def validate_payload(payload):
    if payload.get("schema_version") != 1 or not isinstance(payload.get("records"), list):
        raise ValueError("Unsupported central snapshot")
    if type(payload.get("sequence")) is not int or payload["sequence"] < 0:
        raise ValueError("Invalid snapshot sequence")
    ids, attempts = set(), set()
    for r in payload["records"]:
        if not re.fullmatch(r"[0-9a-f]{64}", r.get("id", "")) or r["id"] in ids:
            raise ValueError("Invalid or duplicate snapshot record ID")
        ids.add(r["id"])
        key = (r.get("attempt_id"), r.get("revision"))
        if not isinstance(key[0], str) or type(key[1]) is not int or key in attempts:
            raise ValueError("Invalid or duplicate attempt/revision")
        attempts.add(key)
        if r.get("problem") not in ("P1", "P2", "P3") or type(r.get("cores")) is not int or r["cores"] not in range(1, 6):
            raise ValueError("Invalid snapshot cell")
        if not re.fullmatch(r"(?:00[1-9]|0[1-9][0-9]|100)", r.get("case_id", "")):
            raise ValueError("Invalid snapshot case")
        if not isinstance(r.get("metrics"), dict) or type(r.get("eligible")) is not bool:
            raise ValueError("Invalid normalized admission record")
    if payload.get("record_count", len(ids)) != len(ids):
        raise ValueError("Snapshot record count mismatch")
    if "records_sha256" in payload and payload["records_sha256"] != digest(canonical(payload["records"])):
        raise ValueError("Snapshot record content digest mismatch")
    expected_ids = digest(("\n".join(sorted(ids)) + "\n").encode())
    if payload.get("record_ids_sha256", expected_ids) != expected_ids:
        raise ValueError("Snapshot ID collection digest mismatch")


def reject_history_regression(previous, candidate):
    if candidate["sequence"] < previous["sequence"]:
        raise ValueError("Snapshot cursor rollback rejected")
    current = {r["id"]: r for r in candidate["records"]}
    for record in previous["records"]:
        if current.get(record["id"]) != record:
            raise ValueError("Snapshot dropped or rewrote historical records")


def unpack(data, manifest):
    if len(data) > MAX_COMPRESSED or len(data) != manifest["payload_size"] or digest(data) != manifest["payload_sha256"]:
        raise ValueError("Snapshot compressed bytes/hash mismatch")
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
        raw = stream.read(MAX_DECODED + 1)
    if len(raw) > MAX_DECODED or len(raw) != manifest["decoded_size"]:
        raise ValueError("Snapshot expanded size mismatch")
    payload = json.loads(raw)
    validate_payload(payload)
    for key in ("sequence", "record_count", "record_ids_sha256", "records_sha256", "snapshot_id"):
        if payload.get(key) != manifest.get(key):
            raise ValueError("Snapshot manifest mismatch: " + key)
    return payload


def publish_files(payload, output):
    output.mkdir(parents=True, exist_ok=True)
    current_file = output / "current.json"
    previous_manifest = json.loads(current_file.read_bytes()) if current_file.exists() else None
    if previous_manifest:
        previous = unpack((output / previous_manifest["payload_file"]).read_bytes(), previous_manifest)
        reject_history_regression(previous, payload)
        if previous["snapshot_id"] == payload["snapshot_id"]:
            return dict(previous_manifest, unchanged=True)
    raw = canonical(payload)
    data = gzip.compress(raw, mtime=0)
    if len(raw) > MAX_DECODED or len(data) > MAX_COMPRESSED:
        raise ValueError("Snapshot exceeds configured size limits")
    name = "snapshot-" + payload["snapshot_id"] + ".json.gz"
    manifest = {k: payload[k] for k in ("schema_version", "generated_at", "sequence", "snapshot_id", "record_count", "record_ids_sha256", "records_sha256", "publisher")}
    manifest.update(payload_file=name, payload_sha256=digest(data), payload_size=len(data), decoded_size=len(raw))
    unpack(data, manifest)
    atomic_write(output / name, data)
    atomic_write(current_file, canonical(manifest) + b"\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = read_central(args.db, frozen_manifest=git_json(args.repo, args.code_commit, "docs/a/source-manifest.json"),
                           algorithms=git_json(args.repo, args.code_commit, "docs/benchmarks/algorithm-registry.json"), code_commit=args.code_commit)
    print(json.dumps(publish_files(payload, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
