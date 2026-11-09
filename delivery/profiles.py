#!/usr/bin/env python3
"""Inspect explicitly selected CLI profiles through official read-only commands.

Never reads credential files, scans home directories, initializes or rebinds.
Official identity output stays in a new private report; stdout has no Bot IDs.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from keeper_common import cli_environment, executable


def inspect_profiles(binary, profiles, output, *, run=subprocess.run):
    output = Path(output).expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('private_report_must_be_outside_release')
    if any(not isinstance(p, str) or not Path(p).is_absolute() for p in profiles):
        raise ValueError('profile_must_be_absolute')
    if len(set(profiles)) != len(profiles):
        raise ValueError('duplicate_profile')
    # Reserve destination before any call; never overwrite an earlier verdict.
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with output.open('x', encoding='utf-8') as stream:
        os.chmod(output, 0o600)
        version = run([binary, '--version'], capture_output=True, text=True, timeout=30, env=cli_environment({}))
        match = re.search(r'\b(\d+)\.(\d+)\.(\d+)\b', version.stdout)
        if version.returncode or not match or tuple(map(int, match.groups())) < (1, 1, 0):
            raise ValueError('unsupported_cli_version')
        if profiles and tuple(map(int, match.groups())) != (1, 3, 0):
            raise ValueError('profile_isolation_requires_version_validation')
        reports = []
        for profile in [None, *profiles]:
            env = cli_environment({'cli_config_dir': profile} if profile else {})
            status = run([binary, 'auth', 'show', '--status'], capture_output=True, text=True, timeout=30, env=env)
            state = status.stdout.strip() if status.returncode == 0 else 'error'
            if state not in ('authorized', 'unauthorized'):
                state = 'error'
            entry = {'cli_config_dir': profile, 'status': state, 'desktop_identity_verified': False}
            if state == 'authorized':
                before = run([binary, 'auth', 'show'], capture_output=True, text=True, timeout=30, env=env)
                ids = re.findall(r'^Bot ID:\s*(\S+)\s*$', before.stdout, re.M)
                identity = run([binary, 'identity', 'whoami'], capture_output=True, text=True, timeout=30, env=env)
                after = run([binary, 'auth', 'show'], capture_output=True, text=True, timeout=30, env=env)
                final_ids = re.findall(r'^Bot ID:\s*(\S+)\s*$', after.stdout, re.M)
                if before.returncode or after.returncode or len(ids) != 1 or final_ids != ids:
                    entry['status'] = 'identity_unstable'
                elif identity.returncode:
                    entry['status'] = 'identity_query_failed'
                else:
                    # CLI 1.3 uses contextual text in JSON, not a stable bot_id
                    # schema. Keep official evidence for the installation Agent.
                    entry['identity'] = json.loads(identity.stdout)
                    entry['cli_bot_id'] = ids[0]
            reports.append(entry)
        json.dump({'schema_version': 2, 'cli_version': match[0], 'profiles': reports,
                   'inventory_scope': 'explicit_profiles_only',
                   'target_selected': False, 'renewal_verified': False}, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return {'ok': all(r['status'] in ('authorized', 'unauthorized') for r in reports),
            'profiles_checked': len(reports), 'authorized_profiles': sum(r['status'] == 'authorized' for r in reports),
            'target_selected': False, 'desktop_identity_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', default='wecom-cli')
    parser.add_argument('--profile', action='append', default=[], help='Known private directory; repeat for each profile')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        result = inspect_profiles(executable(args.cli, 'wecom-cli'), args.profile, args.output)
    except Exception:
        result = {'ok': False, 'error': 'profile_inspection_failed', 'target_selected': False}
    print(json.dumps(result))
    return 0 if result['ok'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
