#!/usr/bin/env python3
"""Portable, standard-library bootstrap. Never operates UI or installs a task."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from keeper_capabilities import CAPABILITY_LABELS
from keeper_bootstrap import authorization_identity, require_target_selection


def detect(system=None):
    system = system or platform.system()
    version = None
    if system == 'Darwin':
        for app in ('企业微信.app', 'WeCom.app'):
            p = Path('/Applications') / app / 'Contents/Info.plist'
            if p.exists():
                with p.open('rb') as f:
                    info = plistlib.load(f)
                version = str(info.get('CFBundleShortVersionString', 'unknown')) + '/' + str(info.get('CFBundleVersion', 'unknown'))
                break
    return {'schema_version': 1, 'platform': system, 'architecture': platform.machine(),
            'python_supported': sys.version_info >= (3, 11), 'client_version': version,
            'backend': 'macos-ax' if system == 'Darwin' else None,
            'status': 'needs_device_acceptance' if system == 'Darwin' else 'unsupported_automation_backend',
            'ui_access': 'not_checked', 'scheduler_installed': False}


def configure(value, destination, system=None, *, selection=None):
    if (system or platform.system()) != 'Darwin':
        raise ValueError('unsupported_automation_backend')
    if not isinstance(value, dict):
        raise ValueError('invalid_input')
    required = {'bot_chat_name', 'authorization_url', 'cli_bot_id', 'target_rows', 'organization_name', 'organization_selector_name'}
    if not required <= set(value) or set(value) - required - {'cli_config_dir', 'wecom_cli', 'wecom_node'}:
        raise ValueError('invalid_input_fields')
    profile = value.get('cli_config_dir')
    if profile is not None and (not isinstance(profile, str) or not profile.strip() or not Path(profile).is_absolute()):
        raise ValueError('invalid_cli_profile')
    selector = value.get('organization_selector_name')
    if selector is not None and (not isinstance(selector, str) or not selector.strip()
                                 or selector.startswith('<') or '\n' in selector):
        raise ValueError('missing_identity_or_organization')
    runtime = {}
    for key, name in [('wecom_cli', 'wecom-cli'), ('wecom_node', 'node')]:
        binary = value[key] if key in value else shutil.which(name)
        if binary is not None and (not isinstance(binary, str) or not binary.strip() or not Path(binary).is_absolute()):
            raise ValueError('invalid_cli_executable')
        if key in value and binary is None:
            raise ValueError('invalid_cli_executable')
        if binary:
            runtime[key] = binary
    for key in required - {'target_rows'}:
        if not isinstance(value[key], str) or not value[key].strip() or value[key].startswith('<') or '\n' in value[key]:
            raise ValueError('missing_identity_or_organization')
    identity = authorization_identity(value['authorization_url'])
    bot = identity['str_aibotid']
    if bot != value['cli_bot_id']:
        raise ValueError('cli_bot_identity_mismatch')
    require_target_selection(selection, value)
    rows = value['target_rows']
    if (not isinstance(rows, list) or not rows or any(not isinstance(r, str) or r not in CAPABILITY_LABELS for r in rows)
            or len(set(rows)) != len(rows)):
        raise ValueError('invalid_permission_allowlist')
    destination = Path(destination).expanduser().resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('private_config_must_be_outside_release')
    key = hashlib.sha256((identity['aibotid'] + ':' + bot).encode()).hexdigest()[:12]
    state = destination.parent / ('state-' + key)
    cfg = {'bot_chat_name': value['bot_chat_name'], **identity, 'authorization_url': value['authorization_url'],
           'target_selection': {k: selection[k] for k in ('selection_source', 'identity_source',
                                'bot_chat_name', 'organization_selector_name', 'authorization_identity')},
           'target_rows': rows, 'chat_history_navigation': True, 'bridge_send_link': False,
           'bridge_monitor': False, 'venv_python': str(ROOT / '.venv/bin/python3'),
           'state_file': str(state / 'state.json'), 'log_file': str(state / 'run.log'),
           'entry_receipt': str(state / 'entry.json'),
           'renew_timeout': 600, 'lock_wait': 10,
           'maintenance': {'within_hours': 24, 'interval_seconds': 3600,
                           'min_renew_interval_seconds': 3600, 'retry_seconds': 300, 'close_window': True}}
    if profile is not None:
        cfg['cli_config_dir'] = profile
    # GUI launchd needs both the CLI launcher and its Node runtime.
    cfg.update(runtime)
    # Preserve declared business intent without enabling unverified navigation.
    cfg['expected_organization'] = value['organization_name']
    if selector is not None:
        cfg['organization_selector_name'] = selector
    # The version-gated organization adapter is opt-in after menu/device validation.
    # Keep its automatic switch off until this exact device has validated that path.
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with destination.open('x', encoding='utf-8') as f:
        os.chmod(destination, 0o600)
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write('\n')
    return {'ok': True, 'status': 'entry_preparation_required', 'permission_count': len(rows),
            'organization_switch': 'requires_device_validation', 'business_verified': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', help='Private local JSON; never paste into shared reports')
    p.add_argument('--output', help='New private config outside the extracted release')
    p.add_argument('--selection', help='Successful private select_target.py result; required for onboarding')
    args = p.parse_args()
    try:
        if bool(args.input) != bool(args.output):
            raise ValueError('input_and_output_required_together')
        if args.input and not args.selection:
            raise ValueError('target_selection_required')
        report = configure(json.loads(Path(args.input).read_text()), args.output,
                           selection=json.loads(Path(args.selection).read_text())) if args.input else detect()
        code = 0 if report.get('ok') or report['status'] == 'needs_device_acceptance' else 3
    except Exception as exc:
        known = str(exc) if type(exc) is ValueError and str(exc) in {
            'unsupported_automation_backend', 'invalid_input', 'invalid_input_fields',
            'missing_identity_or_organization', 'invalid_authorization_url', 'cli_bot_identity_mismatch',
            'invalid_permission_allowlist', 'private_config_must_be_outside_release',
            'input_and_output_required_together', 'invalid_cli_profile', 'invalid_cli_executable',
            'target_selection_required', 'requested_target_mismatch'} else 'input_or_output_unavailable'
        report, code = {'ok': False, 'error': known}, 3
    print(json.dumps(report, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
