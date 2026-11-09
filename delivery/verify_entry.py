#!/usr/bin/env python3
"""Verify an already-prepared chat entry from a different chat/organization.

Never sends messages, grants permissions, changes Bridge or installs a service.
The installer must establish the private chat from the verified Bot details first;
a matching chat title alone does not prove private-vs-group chat type.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from keeper_bootstrap import device_binding, target_binding
from keeper_common import KeeperError, atomic_json, cli_environment, emit_error, executable, gui_lock_path, load_config, process_lock
from keeper_navigation import global_search, heading_matches, open_chat_history
from keeper_organization import ensure_organization, list_organizations
from renew import Renewal


def verify_cli(cfg, *, run=subprocess.run):
    binary = executable(cfg.get('wecom_cli'), 'wecom-cli')
    env = cli_environment(cfg)
    def call(args):
        p = run([binary, *args], env=env, capture_output=True, text=True, timeout=30)
        if p.returncode:
            raise KeeperError('bootstrap_cli_unavailable', 'Official CLI identity check failed')
        return p.stdout
    version = re.search(r'\b(\d+)\.(\d+)\.(\d+)\b', call(['--version']))
    if not version or tuple(map(int, version.groups())) < (1, 1, 0):
        raise KeeperError('bootstrap_cli_unavailable', 'Unsupported CLI version')
    if cfg.get('cli_config_dir') and version[0] != '1.3.0':
        raise KeeperError('bootstrap_cli_unavailable', 'Validate profile isolation for this CLI version first')
    if call(['auth', 'show', '--status']).strip() != 'authorized':
        raise KeeperError('bootstrap_bot_not_bound', 'Select or initialize the intended Bot before preparing its entry')
    ids = re.findall(r'^Bot ID:\s*(\S+)\s*$', call(['auth', 'show']), re.M)
    if ids != [cfg['str_aibotid']]:
        raise KeeperError('bootstrap_cli_identity_mismatch', 'Selected CLI profile does not match the target Bot')


def verify_navigation(cfg, ax, *, engine=None):
    """UI-only verification; caller owns the Keeper lock, not a Bridge lease."""
    if not cfg.get('organization_selector_name'):
        raise KeeperError('bootstrap_organization_required', 'Record the exact native organization menu name first')
    active = dict(cfg, organization_navigation='sidebar-5.0.13', bridge_send_link=False)
    engine = engine or Renewal(active, ax)
    native, engine.app = ax.application()
    result = {'ok': False, 'mode': 'entry-verification', 'renewal_verified': False,
              'authorization_changed': False, 'messages_sent': False,
              'entry_location': 'configured_bot_conversation',
              'private_chat_type': 'must_be_confirmed_by_installer_from_bot_details',
              'runtime_human_or_agent_clicks': False}
    opened = False
    failure = None
    try:
        if engine.select_window() is not None:
            raise KeeperError('bootstrap_cold_start_required', 'Close the target page and start from another chat or organization')
        organizations = list_organizations(engine, native)
        selected = [row['name'] for row in organizations if row['selected']]
        wanted = active['organization_selector_name']
        if len(selected) != 1 or sum(row['name'] == wanted for row in organizations) != 1:
            raise KeeperError('bootstrap_organization_unverified', 'Target must match one exact native organization menu row')
        initial = [w for w in ax.ax_get(engine.app, 'AXWindows') or [] if global_search(engine, w) is not None]
        if len(initial) != 1:
            raise KeeperError('bootstrap_cold_start_required', 'Start in the normal Messages view of another conversation')
        if selected == [wanted] and heading_matches(engine, initial[0], global_search(engine, initial[0])):
            raise KeeperError('bootstrap_cold_start_required', 'Start from another chat or another organization')
        result['cold_start_verified'] = True
        ensure_organization(engine, native)
        open_chat_history(engine, native)
        windows = [w for w in ax.ax_get(engine.app, 'AXWindows') or [] if global_search(engine, w) is not None]
        if len(windows) != 1 or not heading_matches(engine, windows[0], global_search(engine, windows[0])):
            raise KeeperError('bootstrap_chat_changed', 'Target conversation changed before entry inspection')
        links = engine.visible_links(windows)
        if not links:
            raise KeeperError('bootstrap_entry_missing', 'Prepare the renewal link in this Bot private chat before retrying')
        result.update(conversation_header_verified=True, link_identity_verified=True)
        opened = True
        # Open the link just verified in this chat, not a same-Bot link in
        # another window that happens to be visible elsewhere on the desktop.
        chat = windows[0]
        engine.focus_window(native, chat)
        if not heading_matches(engine, chat, global_search(engine, chat)):
            raise KeeperError('bootstrap_chat_changed', 'Conversation changed before opening the entry')
        links = engine.visible_links([chat])
        if not links:
            raise KeeperError('bootstrap_entry_missing', 'Verified chat link disappeared')
        _, link, _ = max(links, key=lambda item: item[0])
        ax.click(link, chat)
        window = engine.wait(engine.select_window, lambda value: value is not None, 'page_not_open')
        engine.bound(window)
        rows = engine.wait(lambda: engine.read_rows(window),
                           lambda values: all(r['status'] in ('authorized', 'expired') for r in values.values()),
                           'rows_incomplete')
        result.update(page_identity_verified=True,
                      rows={n: {'status': r['status'], 'expiry': r['expiry'].isoformat(timespec='minutes')
                                if r['expiry'] else None} for n, r in rows.items()})
        # The same bare “授权” button can mean an expired grant or a scope
        # never granted to this Bot. Do not turn first-run discovery into an
        # unattended initial grant without an established expiry baseline.
        missing_baseline = [name for name, row in rows.items() if row['expiry'] is None]
        if missing_baseline:
            result['authorization_baseline_required'] = missing_baseline
            raise KeeperError('bootstrap_authorization_baseline_required',
                              'Entry found; selected permissions have no expiry evidence. Resolve initial authorization before scheduling')
        closed, _ = engine.close_window()
        opened = False
        if not closed.get('closed'):
            raise KeeperError('bootstrap_cleanup_failed', 'Opened permission page was not verified closed')
        result['cleanup_verified'] = True
        # Recheck native selection after closing; never use Bridge's cache.
        selected_after = [r['name'] for r in list_organizations(engine, native) if r['selected']]
        if selected_after != [wanted]:
            raise KeeperError('bootstrap_organization_changed', 'Organization changed during entry verification')
        result.update(ok=True, organization_verified=True, organization=wanted)
        return result
    except Exception as exc:
        failure = exc
        exc.entry_verification = result
        raise
    finally:
        if opened:
            try:
                closed, _ = engine.close_window()
                result['cleanup_verified'] = closed.get('closed') is True
            except Exception:
                result['cleanup_verified'] = False
                if failure is None:
                    raise KeeperError('bootstrap_cleanup_failed', 'Could not close the verified permission page') from None


def verify_and_save(cfg, ax):
    path = Path(cfg['_config_path'])
    original = path.read_bytes()
    receipt_path = cfg.get('entry_receipt')
    if not receipt_path:
        raise KeeperError('bootstrap_config_required', 'Use onboard.py to create a draft with an entry receipt path')
    # A failed revalidation must not leave an old successful installation verdict.
    atomic_json(receipt_path, {'schema_version': 1, 'ok': False, 'status': 'verification_in_progress'})
    try:
        verify_cli(cfg)
        with process_lock(gui_lock_path(), cfg['lock_wait']):
            result = verify_navigation(cfg, ax)
        if path.read_bytes() != original:
            raise KeeperError('bootstrap_config_changed', 'Configuration changed during verification; no receipt accepted')
        active = {**cfg, 'organization_navigation': 'sidebar-5.0.13'}
        active.pop('_config_path', None)
        atomic_json(path, active)
        result.update(schema_version=1, cli_identity_verified=True, binding=target_binding(active),
                      device=device_binding(), verified_at=datetime.now().isoformat(timespec='seconds'))
        atomic_json(receipt_path, result)
        return result
    except Exception as exc:
        failure, _ = emit_error(exc)
        atomic_json(receipt_path, {**failure, 'schema_version': 1})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    args = p.parse_args()
    try:
        if sys.platform != 'darwin':
            raise KeeperError('unsupported_platform', 'Entry navigation requires the macOS adapter', 3)
        cfg = load_config(args.config)
        import keeper_ax as ax
        result = verify_and_save(cfg, ax)
        code = 0
    except Exception as exc:
        result, code = emit_error(exc)
        if hasattr(exc, 'entry_verification'):
            result['entry_verification'] = exc.entry_verification
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
