"""Verify this synthesis delivery only; never imports author/evaluator code."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys


def main() -> int:
    root = Path(__file__).resolve().parent
    try:
        manifest = json.loads((root / 'DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))
        failures: list[str] = []
        for entry in manifest['files']:
            path = root / entry['path']
            if not path.resolve().is_relative_to(root):
                failures.append(f"unsafe path: {entry['path']}")
                continue
            if not path.is_file():
                failures.append(f"missing: {entry['path']}")
                continue
            data = path.read_bytes()
            if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                failures.append(f"mismatch: {entry['path']}")
        if failures:
            print('\n'.join(failures), file=sys.stderr)
            return 1
        print(f"Verified {len(manifest['files'])} synthesis files. Zero evaluator or author-code calls.")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Verification failed: {exc}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
