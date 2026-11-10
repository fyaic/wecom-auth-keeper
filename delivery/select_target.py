#!/usr/bin/env python3
"""Match an explicitly requested, UI-identified Bot to existing CLI profiles.

Pure private-file processing: never chooses the default because it is authorized,
never changes the requested Bot, initializes a binding, sends or operates UI.
The installer records actual user intent and native-page evidence; this is an
installation record, not an independent attestation of those observations.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from keeper_bootstrap import authorization_identity

_NO_PROFILE_CHOICE = object()


def select(target, inventory, *, profile_choice=_NO_PROFILE_CHOICE):
    if not isinstance(target, dict) or target.get('selection_source') not in {'user_request', 'business_service'}:
        raise ValueError('explicit_target_required')
    if target.get('identity_source') != 'native_selected_bot_permission_page':
        raise ValueError('selected_bot_ui_identity_required')
    for key in ('bot_chat_name', 'organization_selector_name'):
        value = target.get(key)
        if not isinstance(value, str) or not value.strip() or '\n' in value or value.startswith('<'):
            raise ValueError('explicit_target_required')
    identity = authorization_identity(target.get('authorization_url'))
    if not isinstance(inventory, dict) or inventory.get('schema_version') != 2:
        raise ValueError('profile_inventory_requires_refresh')
    profiles = inventory.get('profiles')
    if not isinstance(profiles, list) or not profiles:
        raise ValueError('invalid_profile_inventory')
    paths = []
    for row in profiles:
        if not isinstance(row, dict) or 'cli_config_dir' not in row:
            raise ValueError('invalid_profile_inventory')
        path = row.get('cli_config_dir')
        if path is not None and (not isinstance(path, str) or not path.strip() or not Path(path).is_absolute()):
            raise ValueError('invalid_profile_inventory')
        paths.append(path)
    if len(set(paths)) != len(paths):
        raise ValueError('invalid_profile_inventory')
    matches = [r for r in profiles if r.get('status') == 'authorized'
               and r.get('cli_bot_id') == identity['str_aibotid']]
    identity_matching_profile_count = len(matches)
    choice_source = 'unique_identity_match' if len(matches) == 1 else 'not_selected'
    if profile_choice is not _NO_PROFILE_CHOICE:
        if profile_choice is not None and (not isinstance(profile_choice, str)
                or not profile_choice.strip() or not Path(profile_choice).is_absolute()):
            raise ValueError('profile_must_be_absolute')
        # A user's profile choice only narrows already identity-matched official
        # inventory entries. It never changes the requested Bot or manufactures
        # a missing/unauthorized profile, including when choosing the default.
        matches = [r for r in matches if r['cli_config_dir'] == profile_choice]
        if not matches:
            raise ValueError('requested_profile_not_matching_target')
        choice_source = 'explicit_default' if profile_choice is None else 'explicit_profile'
    status = ('target_profile_selected' if len(matches) == 1 else
              'target_profile_ambiguous' if matches else 'target_profile_not_found')
    report = {'schema_version': 1, 'ok': len(matches) == 1, 'status': status,
              'selection_source': target['selection_source'], 'identity_source': target['identity_source'],
              'bot_chat_name': target['bot_chat_name'], 'organization_selector_name': target['organization_selector_name'],
              'authorization_url': target['authorization_url'], 'authorization_identity': identity,
              'profiles_checked': len(profiles), 'matching_profile_count': len(matches),
              'identity_matching_profile_count': identity_matching_profile_count,
              'profile_choice_source': choice_source,
              'inventory_scope': 'explicit_profiles_only', 'requested_target_changed': False,
              'desktop_creator_verified': False, 'renewal_verified': False}
    if len(matches) == 1:
        report['cli_config_dir'] = matches[0]['cli_config_dir']
        report['cli_bot_id'] = matches[0]['cli_bot_id']
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', required=True, help='Private user-intent/native Bot evidence JSON')
    p.add_argument('--profiles', required=True, help='Private profiles.py inventory JSON')
    p.add_argument('--output', required=True, help='New private selection JSON outside release')
    choice = p.add_mutually_exclusive_group()
    choice.add_argument('--profile', help='Explicitly choose an inventoried matching profile by absolute path')
    choice.add_argument('--default-profile', action='store_true', help='Explicitly choose the inventoried default profile')
    args = p.parse_args()
    try:
        output = Path(args.output).expanduser().resolve()
        if output == ROOT or ROOT in output.parents:
            raise ValueError('private_report_must_be_outside_release')
        profile_choice = None if args.default_profile else args.profile if args.profile is not None else _NO_PROFILE_CHOICE
        result = select(json.loads(Path(args.target).read_text()), json.loads(Path(args.profiles).read_text()),
                        profile_choice=profile_choice)
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with output.open('x', encoding='utf-8') as f:
            os.chmod(output, 0o600)
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write('\n')
        public = {k: result[k] for k in ('ok', 'status', 'profiles_checked', 'matching_profile_count',
                                        'requested_target_changed', 'renewal_verified')}
    except Exception as exc:
        known = {'explicit_target_required', 'selected_bot_ui_identity_required', 'invalid_authorization_url',
                 'profile_inventory_requires_refresh', 'invalid_profile_inventory', 'private_report_must_be_outside_release',
                 'profile_must_be_absolute', 'requested_profile_not_matching_target'}
        public = {'ok': False, 'error': str(exc) if type(exc) is ValueError and str(exc) in known else 'target_selection_failed'}
    print(json.dumps(public, ensure_ascii=False))
    return 0 if public['ok'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
