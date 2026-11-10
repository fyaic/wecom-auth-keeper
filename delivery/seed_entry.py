#!/usr/bin/env python3
"""Send one prepared entry in the installer's already-verified Bot private chat.

No navigation, permission changes, CLI binding or service changes. The installer
must establish the private-chat type from native Bot details. --send-confirmed
acknowledges that fact and the user's specific send request; it is not a prompt
for new permission and is never called by the hourly renewal service.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from keeper_accessibility import exposed_tree
from keeper_bootstrap import entry_message, target_binding
from keeper_common import KeeperError, atomic_json, emit_error, gui_lock_path, load_config, process_lock
from keeper_navigation import chat_composer, chat_header, global_search
from renew import Renewal
from delivery.verify_entry import verify_cli


def seed_current_chat(cfg, ax, *, engine=None):
    engine = engine or Renewal(cfg, ax)
    native, engine.app = ax.application()
    message = entry_message(cfg)
    journal = Path(cfg['state_file'] + '.entry-send.json')
    binding = target_binding(cfg)
    windows = [w for w in ax.ax_get(engine.app, 'AXWindows') or [] if global_search(engine, w) is not None]
    if len(windows) != 1:
        raise KeeperError('entry_message_view_required', 'Open the verified Bot private chat first')
    window = windows[0]

    def current():
        if window not in (ax.ax_get(engine.app, 'AXWindows') or []):
            raise KeeperError('entry_chat_changed', 'Chat window changed')
        if chat_header(engine, window) != cfg['bot_chat_name']:
            raise KeeperError('entry_header_mismatch', 'Read the actual native AX chat header; do not guess spaces from a screenshot')
        composer = chat_composer(engine, window)
        if composer is None:
            raise KeeperError('entry_message_view_required', 'Expected message toolbar and one editable bottom composer')
        return composer

    composer = current()
    if engine.visible_links([window]):
        atomic_json(journal, {'schema_version': 1, 'binding': binding, 'status': 'visible_entry_verified'})
        return {'ok': True, 'mode': 'seed-current-chat', 'messages_sent': 0,
                'link_identity_verified': True, 'entry_reused': True, 'renewal_verified': False}
    if journal.exists():
        # A timeout/crash after Return has an unknown outcome. Never resend
        # automatically; navigate to history and inspect the earlier attempt.
        raise KeeperError('entry_send_already_attempted', 'Inspect the prior entry attempt before retrying; no duplicate sent')
    if ax.ax_get(composer, 'AXValue') not in ('', None):
        raise KeeperError('entry_draft_present', 'Existing draft preserved; no input or send')
    engine.focus_window(native, window, 'entry_focus_lost')
    composer = current()
    if ax.ax_get(composer, 'AXValue') not in ('', None):
        raise KeeperError('entry_draft_present', 'Existing draft preserved; no input or send')
    ax.click(composer, window)
    current()
    if ax.ax_get(engine.app, 'AXFocusedUIElement') != composer:
        raise KeeperError('entry_composer_focus_lost', 'Composer did not receive focus')
    if ax.ax_get(composer, 'AXValue') not in ('', None):
        raise KeeperError('entry_draft_present', 'Existing draft preserved; no input or send')
    atomic_json(journal, {'schema_version': 1, 'binding': binding, 'status': 'preparing_draft'})
    ax.paste_composer(native, engine.app, window, composer, message)
    def draft():
        if current() != composer:
            raise KeeperError('entry_chat_changed', 'Composer changed')
        return ax.ax_get(composer, 'AXValue')
    engine.wait(draft, lambda value: value == message, 'entry_draft_readback_failed', timeout=5)
    current()
    atomic_json(journal, {'schema_version': 1, 'binding': binding, 'status': 'send_attempt_pending'})
    ax.submit_composer(native, engine.app, window, composer, message)
    def delivered():
        current()
        return not ax.ax_get(composer, 'AXValue') and bool(engine.visible_links([window]))
    engine.wait(delivered, bool, 'entry_send_unconfirmed', timeout=10)
    atomic_json(journal, {'schema_version': 1, 'binding': binding, 'status': 'visible_entry_verified'})
    return {'ok': True, 'mode': 'seed-current-chat', 'messages_sent': 1,
            'link_identity_verified': True, 'entry_reused': False, 'renewal_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--send-confirmed', action='store_true', required=True,
                        help='Installer verified this Bot private chat and user authorized its entry message')
    args = parser.parse_args()
    try:
        cfg = load_config(args.config)
        verify_cli(cfg)
        import keeper_ax as ax
        with process_lock(gui_lock_path(), cfg['lock_wait']):
            _, app = ax.application()
            with exposed_tree(ax, app):
                result = seed_current_chat(cfg, ax)
        code = 0
    except Exception as exc:
        result, code = emit_error(exc)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
