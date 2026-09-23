"""Verify round-1 source bytes and optionally extract the official cases."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "docs/a/source-manifest.json").read_text(encoding="utf-8"))
    archive = ROOT / manifest["case_archive"]["path"]
    if digest(archive.read_bytes()) != manifest["case_archive"]["sha256"]:
        raise ValueError("Case archive hash mismatch")
    pdf = ROOT / manifest["pdf"]["path"]
    if digest(pdf.read_bytes()) != manifest["pdf"]["sha256"]:
        raise ValueError("Problem PDF hash mismatch")
    official = ROOT / "data/raw/a/official"
    records = manifest["files"]
    expected_cases = {r["path"] for r in records if Path(r["path"]).name.startswith("case_")}
    with ZipFile(archive) as z:
        if set(z.namelist()) != expected_cases or len(z.namelist()) != len(expected_cases):
            raise ValueError("Unexpected or duplicate archive entries")
        checked = []
        for r in records:
            relative = Path(r["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe manifest path")
            raw = z.read(r["path"]) if r["path"] in expected_cases else (official / relative).read_bytes()
            if len(raw) != r["bytes"] or digest(raw) != r["sha256"]:
                raise ValueError(f"Source mismatch: {r['path']}")
            checked.append((r, raw))
        # Check existing targets before writing any missing case; never overwrite.
        if args.extract:
            for r, raw in checked:
                target = official / r["path"]
                if r["path"] in expected_cases and target.exists() and target.read_bytes() != raw:
                    raise ValueError(f"Refusing to overwrite changed original: {r['path']}")
            for r, raw in checked:
                target = official / r["path"]
                if r["path"] in expected_cases and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as f:
                        f.write(raw)
    material = "".join(r["path"] + "\t" + r["sha256"] + "\n" for r in sorted(records, key=lambda r: r["path"]) if r["path"].startswith("code/"))
    if digest(material.encode()) != manifest["official_code_hash"]:
        raise ValueError("Code hash definition mismatch")
    print(json.dumps({"source_files_verified": len(records), "cases_verified": len(expected_cases), "cases_extracted": args.extract, "official_code_hash": manifest["official_code_hash"], "semantic_tests_run": False}))


if __name__ == "__main__":
    main()
