"""Portable first-run entry state. No UI, credential reads or network requests."""
import hashlib
import json
import os
from pathlib import Path
import platform
from urllib.parse import urlencode

ENTRY_MARKER = '【自动续期入口】'


def target_binding(cfg):
    values = {key: cfg.get(key) for key in (
        'aibotid', 'str_aibotid', 'bot_chat_name', 'cli_config_dir',
        'organization_selector_name', 'organization_navigation', 'target_rows', 'venv_python', 'wecom_cli', 'wecom_node')}
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def device_binding():
    # A local setup receipt, not a security attestation. Prevent accidental reuse
    # under another machine/account/path; never publish the underlying values.
    value = [platform.node(), str(Path.home().resolve()), getattr(os, 'getuid', lambda: None)()]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def entry_message(cfg):
    for key in ('aibotid', 'str_aibotid', 'bot_chat_name', 'organization_selector_name'):
        value = cfg.get(key)
        if not isinstance(value, str) or not value.strip() or value.startswith('<'):
            raise ValueError('target_binding_incomplete')
    if not cfg['aibotid'].isdigit():
        raise ValueError('target_binding_incomplete')
    url = 'https://work.weixin.qq.com/ai/aiHelper/authorizationList?' + urlencode({
        'from': 'chat', 'forceInnerBrowser': '1', 'aibotid': cfg['aibotid'],
        'str_aibotid': cfg['str_aibotid'], 'type': '1'})
    return ENTRY_MARKER + '\n此消息用于本设备的权限续期，请保留，无需回复。\n' + url + '\n'


def entry_status(cfg):
    path = cfg.get('entry_receipt')
    if path is None:
        return {'ok': True, 'status': 'legacy_config_without_entry_gate'}
    try:
        receipt = json.loads(Path(path).read_text())
    except (OSError, ValueError, TypeError):
        return {'ok': False, 'status': 'entry_preparation_required'}
    if not isinstance(receipt, dict) or receipt.get('ok') is not True:
        return {'ok': False, 'status': 'entry_verification_required'}
    required = ('cli_identity_verified', 'organization_verified', 'conversation_header_verified',
                'link_identity_verified', 'page_identity_verified', 'cold_start_verified', 'cleanup_verified')
    if (receipt.get('schema_version') != 1 or receipt.get('binding') != target_binding(cfg)
            or receipt.get('device') != device_binding()
            or any(receipt.get(key) is not True for key in required)
            or receipt.get('entry_location') != 'configured_bot_conversation'):
        return {'ok': False, 'status': 'entry_binding_changed'}
    return {'ok': True, 'status': 'entry_navigation_verified', 'renewal_verified': False}


def require_entry(cfg):
    result = entry_status(cfg)
    if not result['ok']:
        from keeper_common import KeeperError
        raise KeeperError('bootstrap_incomplete',
                          'Prepare the target Bot, its organization and private-chat renewal link; then run entry-verify', 3)
