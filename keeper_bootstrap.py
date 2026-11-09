"""Portable first-run entry state. No UI, credential reads or network requests."""
import hashlib
import json
import os
from pathlib import Path
import platform
from urllib.parse import urlencode, urlsplit, parse_qs

ENTRY_MARKER = '【自动续期入口】'


def validate_target_selection(selection):
    """Reject incomplete/ambiguous installer records before using a profile."""
    if (not isinstance(selection, dict) or selection.get('schema_version') != 1
            or selection.get('ok') is not True or selection.get('status') != 'target_profile_selected'
            or selection.get('matching_profile_count') != 1
            or selection.get('requested_target_changed') is not False
            or 'cli_config_dir' not in selection):
        raise ValueError('target_selection_required')
    if (selection.get('selection_source') not in {'user_request', 'business_service'}
            or selection.get('identity_source') != 'native_selected_bot_permission_page'):
        raise ValueError('target_selection_required')
    profile = selection['cli_config_dir']
    if profile is not None and (not isinstance(profile, str) or not profile.strip() or not Path(profile).is_absolute()):
        raise ValueError('target_selection_required')
    if any(not isinstance(selection.get(k), str) or not selection[k].strip()
           for k in ('bot_chat_name', 'organization_selector_name')):
        raise ValueError('target_selection_required')
    try:
        identity = authorization_identity(selection.get('authorization_url'))
    except ValueError:
        raise ValueError('target_selection_required') from None
    if selection.get('authorization_identity') != identity or selection.get('cli_bot_id') != identity['str_aibotid']:
        raise ValueError('target_selection_required')


def require_target_selection(selection, value):
    """Bind onboarding to explicit user intent, not whichever CLI is default."""
    validate_target_selection(selection)
    identity = authorization_identity(value.get('authorization_url'))
    if (selection.get('authorization_identity') != identity
            or selection.get('cli_bot_id') != value.get('cli_bot_id')
            or selection.get('cli_config_dir') != value.get('cli_config_dir')
            or selection.get('bot_chat_name') != value.get('bot_chat_name')
            or selection.get('organization_selector_name') != value.get('organization_selector_name')):
        raise ValueError('requested_target_mismatch')


def authorization_identity(value):
    """Validate an official URL without rebuilding its client routing parameters."""
    try:
        if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value):
            raise ValueError
        url = urlsplit(value)
        query = parse_qs(url.query, keep_blank_values=True)
        numeric, opaque = query.get('aibotid', []), query.get('str_aibotid', [])
        if (url.scheme != 'https' or url.hostname != 'work.weixin.qq.com'
                or url.port not in (None, 443) or url.username or url.password or url.fragment
                or url.path != '/ai/aiHelper/authorizationList'
                or len(numeric) != 1 or not numeric[0].isascii() or not numeric[0].isdigit()
                or len(opaque) != 1 or not opaque[0]
                or any(c.isspace() or ord(c) < 32 for c in opaque[0])):
            raise ValueError
        return {'aibotid': numeric[0], 'str_aibotid': opaque[0]}
    except (TypeError, ValueError):
        raise ValueError('invalid_authorization_url') from None


def target_binding(cfg):
    values = {key: cfg.get(key) for key in (
        'aibotid', 'str_aibotid', 'bot_chat_name', 'cli_config_dir',
        'organization_selector_name', 'organization_navigation', 'target_rows', 'venv_python', 'wecom_cli', 'wecom_node')}
    # Preserve old receipts for configs without this newly recorded field.
    if 'authorization_url' in cfg:
        values['authorization_url'] = cfg['authorization_url']
    if 'target_selection' in cfg:
        values['target_selection'] = cfg['target_selection']
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def device_binding():
    # A local setup receipt, not a security attestation. Prevent accidental reuse
    # under another machine/account/path; never publish the underlying values.
    value = [platform.node(), str(Path.home().resolve()), getattr(os, 'getuid', lambda: None)()]
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def authorization_url(cfg):
    """One URL contract for installation messages and the legacy Bridge sender."""
    if 'authorization_url' in cfg:
        url = cfg['authorization_url']
        if authorization_identity(url) != {k: cfg[k] for k in ('aibotid', 'str_aibotid')}:
            raise ValueError('cli_bot_identity_mismatch')
    elif cfg.get('entry_receipt'):
        raise ValueError('official_authorization_url_required')
    else:
        # Compatibility only for already-deployed legacy configs. New installs
        # must retain the official URL; type/native parameters are not ours to invent.
        url = 'https://work.weixin.qq.com/ai/aiHelper/authorizationList?' + urlencode({
            'from': 'chat', 'forceInnerBrowser': '1', 'aibotid': cfg['aibotid'],
            'str_aibotid': cfg['str_aibotid'], 'type': '1'})
    return url


def entry_message(cfg):
    for key in ('aibotid', 'str_aibotid', 'bot_chat_name', 'organization_selector_name'):
        value = cfg.get(key)
        if not isinstance(value, str) or not value.strip() or value.startswith('<'):
            raise ValueError('target_binding_incomplete')
    if not cfg['aibotid'].isdigit():
        raise ValueError('target_binding_incomplete')
    return ENTRY_MARKER + '\n此消息用于本设备的权限续期，请保留，无需回复。\n' + authorization_url(cfg) + '\n'


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
