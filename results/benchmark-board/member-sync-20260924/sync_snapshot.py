"""Add the published central snapshot to a member ledger, preserving other data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3],
                        help="Checkout containing the website code to use")
    parser.add_argument("--state", type=Path, required=True,
                        help="Existing member state directory; never deleted or replaced")
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    manifest = json.loads(Path(__file__).with_name("manifest.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(repo / "src/benchmark_board"))
    import core
    from app import blob, git, load_feed
    from core import Ledger, safe_path, sha

    if getattr(core, "MAX_EXPANDED_JSON", 0) < 128 * 1024 * 1024:
        raise SystemExit("Update the website receiver to a241394 or a later compatible release BEFORE importing P1 data. No ledger was opened or modified.")

    # Validate and obtain all feed bytes before adding any records. The existing
    # importer verifies original artifacts and appends revisions transactionally.
    for source in manifest["feeds"]:
        commit, path = source["commit"], source["path"]
        if not sha(commit, 40):
            raise ValueError("Expected fixed 40-character source commit")
        safe_path(path)
        try:
            git(repo, "cat-file", "-e", commit + "^{commit}")
        except subprocess.CalledProcessError:
            if args.no_fetch:
                raise
            git(repo, "fetch", "--no-tags", "origin", commit, timeout=180)
        if hashlib.sha256(blob(repo, commit, path)).hexdigest() != source["feed_sha256"]:
            raise ValueError("Feed SHA256 differs: " + path)

    frozen = json.loads((repo / "docs/a/source-manifest.json").read_text(encoding="utf-8"))
    admission = json.loads((repo / "docs/benchmarks/board-calibrations.json").read_text(encoding="utf-8"))
    ledger = Ledger(args.state.resolve(), frozen, admission)
    before = {r["id"] for r in ledger.records()}
    added = 0
    for source in manifest["feeds"]:
        receipt = load_feed(ledger, repo, source["commit"], source["path"])
        added += receipt["added"]
        print(json.dumps({"feed": source["path"], **receipt}, ensure_ascii=False), flush=True)

    rows = ledger.records()
    by_id = {r["id"]: r for r in rows}
    expected = set(manifest["record_ids"])
    missing = sorted(expected - by_id.keys())
    lost_existing = sorted(before - by_id.keys())
    projection = [{k: by_id[rid].get(k) for k in manifest["admission_projection_fields"]}
                  for rid in sorted(expected & by_id.keys())]
    for row in projection:
        row["metrics"] = {k: (row.get("metrics") or {}).get(k)
                          for k in manifest["admission_projection_metrics"]}
    projection_hash = hashlib.sha256(json.dumps(projection, ensure_ascii=False, sort_keys=True,
                                                separators=(",", ":")).encode()).hexdigest()
    same_validation = projection_hash == manifest["admission_projection_sha256"]
    result = {
        "snapshot_utc": manifest["snapshot_utc"],
        "receiver_code_commit": git(repo, "rev-parse", "HEAD").decode().strip(),
        "snapshot_records": len(expected), "local_records": len(rows), "added": added,
        "missing_snapshot_ids": missing, "lost_existing_ids": lost_existing,
        "extra_local_records_preserved": len(by_id.keys() - expected),
        "same_snapshot_admission_and_metrics": same_validation,
        "admission_projection_sha256": projection_hash,
        "record_ids_sha256": hashlib.sha256(("\n".join(sorted(expected & by_id.keys())) + "\n").encode()).hexdigest(),
        "solver_calls": 0, "evaluator_calls": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if missing or lost_existing or not same_validation:
        raise SystemExit("Snapshot verification differs. Keep the ledger and report this receipt; do not clear or overwrite it.")


if __name__ == "__main__":
    main()
