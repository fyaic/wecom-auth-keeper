#!/usr/bin/env python3
"""Read the selected existing CLI profile and recover its official renewal URL.

No credential files, login, binding, messages, UI or permissions are changed.
Identity and the exact URL stay in a new private report outside the release.
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
from keeper_bootstrap import authorization_identity, validate_target_selection
from keeper_common import cli_environment, executable


def official_url(response, bot_id):
    """Only the official CLI's structured help_message is a URL source."""
    message = response.get('help_message', '')
    if not isinstance(message, str):
        raise ValueError('invalid_cli_response')
    urls = set(re.findall(r'https://[^\s<>"\'\]\)]+', message))
    matches = []
    for url in urls:
        try:
            ids = authorization_identity(url)
        except ValueError:
            continue
        if ids['str_aibotid'] != bot_id:
            raise ValueError('cli_bot_identity_mismatch')
        matches.append(url)
    if len(matches) != 1:
        raise ValueError('official_authorization_url_unavailable')
    return matches[0]


def inspect_existing(cfg, output, *, run=subprocess.run):
    output = Path(output).expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('private_report_must_be_outside_release')
    profile = cfg.get('cli_config_dir')
    if profile is not None and (not isinstance(profile, str) or not profile.strip() or not Path(profile).is_absolute()):
        raise ValueError('profile_must_be_absolute')
    env = cli_environment(cfg)
    binary = executable(cfg.get('wecom_cli'), 'wecom-cli')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Reserve before any external call. Never silently replace prior evidence.
    with output.open('x', encoding='utf-8') as stream:
        os.chmod(output, 0o600)
        def call(args, *, allow_error=False):
            p = run([binary, *args], env=env, capture_output=True, text=True, timeout=30)
            if p.returncode and not allow_error:
                raise ValueError('existing_cli_unavailable')
            return p
        version = re.search(r'\b(\d+)\.(\d+)\.(\d+)\b', call(['--version']).stdout)
        if not version or tuple(map(int, version.groups())) < (1, 1, 0):
            raise ValueError('unsupported_cli_version')
        if profile and version[0] != '1.3.0':
            raise ValueError('profile_isolation_requires_version_validation')
        if call(['auth', 'show', '--status']).stdout.strip() != 'authorized':
            raise ValueError('existing_profile_not_authorized')
        def bound_bot():
            ids = re.findall(r'^Bot ID:\s*(\S+)\s*$', call(['auth', 'show']).stdout, re.M)
            if len(ids) != 1:
                raise ValueError('existing_bot_identity_unavailable')
            return ids[0]
        bot_id = bound_bot()
        if cfg.get('expected_bot_id') is not None and bot_id != cfg['expected_bot_id']:
            raise ValueError('requested_target_mismatch')
        identity = json.loads(call(['identity', 'whoami']).stdout)
        result = call(['message', 'aibot', 'sessions', 'list'], allow_error=True)
        response = json.loads(result.stdout)
        if not isinstance(response, dict):
            raise ValueError('invalid_cli_response')
        if bound_bot() != bot_id:
            raise ValueError('cli_profile_changed')
        # Healthy scopes do not necessarily return a link. Do not send a
        # message or invent a failing write to manufacture an error response.
        errcode = response.get('errcode')
        # A newly bound, already-created Bot may have no grant yet (850002).
        # Reuse its official link too, but never call this state an expiry or
        # silently grant it. Entry verification still requires an expiry baseline.
        if errcode not in (850002, 850003):
            raise ValueError('official_authorization_url_unavailable')
        url = official_url(response, bot_id)
        report = {'schema_version': 1, 'cli_version': version[0],
                  'cli_config_dir': profile, 'cli_bot_id': bot_id, 'identity': identity,
                  'authorization_url': url, 'authorization_identity': authorization_identity(url),
                  'url_source': 'official_cli_message_sessions_help_message',
                  'scope_status': {'消息': 'not_authorized' if errcode == 850002 else 'expired'},
                  'authorization_baseline_required': errcode == 850002, 'errcode': errcode,
                  'organization_verified': False, 'desktop_identity_verified': False,
                  'private_chat_verified': False, 'renewal_verified': False}
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return {'ok': True, 'status': 'official_entry_recovered', 'existing_binding_reused': True,
            'messages_sent': False, 'authorization_changed': False,
            'authorization_baseline_required': errcode == 850002,
            'organization_verified': False, 'renewal_verified': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cli', default='wecom-cli')
    p.add_argument('--node', help='Absolute Node path for the npm CLI launcher')
    p.add_argument('--profile', help='Optional cross-check; omitted uses the selection record, not the CLI default')
    p.add_argument('--selection', required=True, help='Successful private select_target.py result')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    try:
        cfg = {'wecom_cli': executable(args.cli, 'wecom-cli')}
        selection = json.loads(Path(args.selection).read_text())
        validate_target_selection(selection)
        if args.profile is not None and args.profile != selection['cli_config_dir']:
            raise ValueError('requested_target_mismatch')
        cfg['expected_bot_id'] = selection['cli_bot_id']
        if args.node:
            cfg['wecom_node'] = executable(args.node, 'node')
        if selection['cli_config_dir'] is not None:
            cfg['cli_config_dir'] = selection['cli_config_dir']
        result = inspect_existing(cfg, args.output)
    except Exception as exc:
        known = {'private_report_must_be_outside_release', 'profile_must_be_absolute',
                 'existing_cli_unavailable', 'unsupported_cli_version', 'profile_isolation_requires_version_validation',
                 'existing_profile_not_authorized', 'existing_bot_identity_unavailable', 'invalid_cli_response',
                 'cli_profile_changed', 'cli_bot_identity_mismatch', 'official_authorization_url_unavailable',
                 'target_selection_required', 'requested_target_mismatch'}
        result = {'ok': False, 'error': str(exc) if type(exc) is ValueError and str(exc) in known else 'existing_entry_inspection_failed',
                  'binding_changed': False, 'renewal_verified': False}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
