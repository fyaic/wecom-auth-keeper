#!/usr/bin/env python3
"""Verify extracted files against the bundled manifest; not a publisher signature."""
import hashlib
import json
from pathlib import Path


def verify(root):
    root = Path(root).resolve()
    try:
        manifest = json.loads((root / 'MANIFEST.json').read_text())
        for name, digest in manifest['files'].items():
            path = (root / name).resolve()
            if root not in path.parents or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return False
        return bool(manifest['files'])
    except (OSError, ValueError, KeyError, TypeError):
        return False


if __name__ == '__main__':
    ok = verify(Path(__file__).resolve().parents[1])
    print(json.dumps({'ok': ok, 'check': 'bundle_integrity', 'publisher_authenticated': False}))
    raise SystemExit(0 if ok else 2)
