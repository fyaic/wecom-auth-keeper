#!/usr/bin/env python3
"""Prepare a private renewal-link message, or inspect first-run readiness. Never send."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from keeper_bootstrap import entry_message, entry_status


def prepare(cfg, output):
    content = entry_message(cfg)
    output = Path(output).expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError('private_message_must_be_outside_release')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with output.open('x', encoding='utf-8') as f:
        output.chmod(0o600)
        f.write(content)
    return {'ok': True, 'sent': False, 'organization': cfg['organization_selector_name'],
            'bot_chat_name': cfg['bot_chat_name'], 'message_file': str(output),
            'next': 'verify_bot_details_then_send_once_to_its_private_chat'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--message-output', help='New private text file; no sending is performed')
    args = p.parse_args()
    try:
        cfg = json.loads(Path(args.config).read_text())
        result = prepare(cfg, args.message_output) if args.message_output else entry_status(cfg)
    except Exception as exc:
        known = {'target_binding_incomplete', 'private_message_must_be_outside_release',
                 'invalid_authorization_url', 'cli_bot_identity_mismatch', 'official_authorization_url_required'}
        result = {'ok': False, 'sent': False,
                  'error': str(exc) if type(exc) is ValueError and str(exc) in known else 'entry_preparation_failed'}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
