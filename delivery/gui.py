#!/usr/bin/env python3
"""Run a bundled acceptance action once in the logged-in user's GUI launchd domain.

This is a temporary job, not the hourly service. It never grants Accessibility.
The same configured Python and public entry points are used by production.
"""
import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def command(action, python, config):
    entries = {'check': ('renew.py', '--check'), 'check-existing': ('renew.py', '--check'),
               'close': ('renew.py', '--close-window'),
               'maintain': ('maintain.py', None), 'discover': ('delivery/discover.py', None),
               'inspect': ('delivery/desktop_inspect.py', None),
               'inspect-expanded': ('delivery/desktop_inspect.py', '--expose-native-tree')}
    entry, flag = entries[action]
    return ([python, str(ROOT / entry), '--config', str(config)] + ([flag] if flag else [])
            + (['--existing-window'] if action == 'check-existing' else []))


def run_once(action, config, evidence):
    if sys.platform != 'darwin':
        raise ValueError('unsupported_automation_backend')
    from keeper_common import executable, load_config
    cfg = load_config(config)
    if os.stat('/dev/console').st_uid != os.getuid():
        raise ValueError('console_user_mismatch')
    evidence = Path(evidence).expanduser().resolve()
    if evidence == ROOT or ROOT in evidence.parents:
        raise ValueError('evidence_must_be_outside_release')
    # New directory prevents stale success logs from being counted as this run.
    evidence.mkdir(mode=0o700, parents=True, exist_ok=False)
    python = executable(cfg.get('venv_python'), sys.executable)
    label = 'com.fyaic.authkeeper.acceptance.' + uuid.uuid4().hex[:12]
    domain = f'gui/{os.getuid()}'
    plist = evidence / 'job.plist'
    stdout, stderr = evidence / 'stdout.json', evidence / 'stderr.log'
    for path in (stdout, stderr):
        path.touch(mode=0o600)
    data = {'Label': label, 'RunAtLoad': True, 'ProgramArguments': command(action, python, cfg['_config_path']),
            'WorkingDirectory': str(ROOT), 'StandardOutPath': str(stdout), 'StandardErrorPath': str(stderr)}
    with plist.open('xb') as f:
        plist.chmod(0o600)
        plistlib.dump(data, f)
    loaded = False
    try:
        subprocess.run(['launchctl', 'bootstrap', domain, str(plist)], check=True, capture_output=True)
        loaded = True
        deadline = time.monotonic() + cfg['renew_timeout'] + 60
        while time.monotonic() < deadline:
            state = subprocess.run(['launchctl', 'print', domain + '/' + label], capture_output=True, text=True)
            if state.returncode:
                raise ValueError('temporary_job_disappeared')
            exit_code = re.search(r'^\s*last exit code = (\d+)\s*$', state.stdout, re.M)
            running = re.search(r'^\s*pid = \d+\s*$', state.stdout, re.M)
            if exit_code and not running:
                try:
                    result = json.loads(stdout.read_text())
                except ValueError:
                    raise ValueError('invalid_gui_result') from None
                code = int(exit_code[1])
                return {'ok': code == 0 and result.get('ok') is True, 'action': action,
                        'launchd_exit_code': code, 'result': result, 'evidence_directory': str(evidence)}
            time.sleep(1)
        raise ValueError('gui_acceptance_timeout')
    finally:
        if loaded:
            unloaded = subprocess.run(['launchctl', 'bootout', domain + '/' + label], capture_output=True)
            if unloaded.returncode:
                raise ValueError('temporary_job_cleanup_failed')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--action', choices=['inspect', 'inspect-expanded', 'discover', 'check', 'check-existing', 'close', 'maintain'], required=True)
    p.add_argument('--evidence-dir', required=True, help='New private directory outside the release')
    args = p.parse_args()
    try:
        result = run_once(args.action, args.config, args.evidence_dir)
    except Exception as exc:
        result = {'ok': False, 'error': 'gui_acceptance_failed'}
        if sys.platform == 'darwin':
            from keeper_common import emit_error
            result, _ = emit_error(exc)
        known = {'unsupported_automation_backend', 'console_user_mismatch', 'evidence_must_be_outside_release',
                 'temporary_job_disappeared', 'invalid_gui_result', 'gui_acceptance_timeout',
                 'temporary_job_cleanup_failed'}
        if type(exc) is ValueError and str(exc) in known:
            result['error'] = str(exc)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
