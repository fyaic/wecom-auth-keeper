#!/usr/bin/env python3
"""Build a clean offline-source ZIP from a tracked allowlist, never the working directory."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['LICENSE', 'AGENTS.md', 'requirements-macos.txt', 'renew.py', 'maintain.py', 'keeper_ax.py',
         'keeper_common.py', 'keeper_navigation.py', 'keeper_organization.py', 'keeper_maintenance.py', 'keeper_accessibility.py',
         'keeper_capabilities.py', 'keeper_cleanup.py', 'config.maintenance.example.json',
         'keeper_bootstrap.py', 'delivery/prepare_entry.py', 'delivery/verify_entry.py', 'delivery/FIRST-RUN.md',
         'delivery/onboard.py', 'delivery/profiles.py', 'delivery/existing_entry.py', 'delivery/verify_bundle.py', 'delivery/gui.py', 'delivery/discover.py',
         'delivery/desktop_inspect.py', 'delivery/START-HERE.md',
         'delivery/AGENT-INSTALL.md', 'delivery/BRIDGE-COORDINATION.md', 'delivery/DESIGN.md', 'delivery/VALIDATION.md', 'delivery/acceptance.example.json']


def build(output):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    content = {}
    for name in FILES:
        committed = subprocess.check_output(['git', 'show', f'{commit}:{name}'], cwd=ROOT)
        if (ROOT / name).read_bytes() != committed:
            raise ValueError('Commit release changes before packaging: ' + name)
        content[name] = committed
    content['START-HERE.md'] = content['delivery/START-HERE.md']
    manifest = {'format': 1, 'source_commit': commit, 'edition': 'agent-preview',
                'support': {'macos': 'requires-device-acceptance', 'windows': 'no-automation-backend'},
                'files': {n: hashlib.sha256(data).hexdigest() for n, data in content.items()}}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(content.items()):
            item = zipfile.ZipInfo('wecom-auth-keeper/' + name, (2026, 11, 6, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            z.writestr(item, data)
        item = zipfile.ZipInfo('wecom-auth-keeper/MANIFEST.json', (2026, 11, 6, 0, 0, 0))
        item.compress_type = zipfile.ZIP_DEFLATED
        item.external_attr = 0o100644 << 16
        z.writestr(item, json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(checksum + '  ' + output.name + '\n')
    return {'archive': str(output), 'sha256': checksum, 'source_commit': commit, 'files': len(content)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    print(json.dumps(build(p.parse_args().output)))
