#!/usr/bin/env python3
"""Observe native controls and official permission pages; never navigate or click.

This is a diagnostic snapshot, safe to request without claiming desktop ownership.
No raw URLs, Bot IDs, conversation text, clipboard or credential files are emitted.
"""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keeper_common import emit_error, load_config
from keeper_accessibility import exposed_tree
from keeper_navigation import sidebar_rows
from keeper_organization import menu_rows
from renew import Renewal, target_url

NATIVE_LABELS = {'消息', '机器人', '智能机器人', '管理机器人', '我的机器人', '机器人详情', '管理', '去管理', '去使用', '详情', '可使用权限',
                 '查找聊天记录', '关闭聊天记录', '查看更多机器人', '机器人资料', '发消息'}
PERMISSION_LABELS = {'授权', '已授权', '取消授权', '确认', '确定', '同意', '重新授权'}


def native_labels(ax, node):
    """Return fixed diagnostic labels, never a raw composite card description.

    Native 5.0.13 cards can combine headings and descriptions in one AX value.
    A contained label is only an observation; it does not identify a click target.
    Short labels require equality to avoid treating e.g. 机器人详情 as 详情.
    """
    matches = {}
    for attribute in ('AXTitle', 'AXValue', 'AXDescription', 'AXHelp'):
        value = ax.ax_get(node, attribute)
        if not isinstance(value, str):
            continue
        value = value.strip()
        for name in NATIVE_LABELS:
            exact = value == name
            if exact or (len(name) >= 4 and name in value):
                entry = matches.setdefault(name, {'label': name, 'match': 'contained', 'attributes': []})
                entry['attributes'].append(attribute)
                if exact:
                    entry['match'] = 'exact'
    return [matches[name] for name in sorted(matches)]


def official_page(value):
    try:
        url = urlsplit(str(value or ''))
        query = parse_qs(url.query)
        return (url.scheme == 'https' and url.hostname == 'work.weixin.qq.com'
                and url.port in (None, 443) and not url.username and not url.password
                and url.path == '/ai/aiHelper/authorizationList'
                and all(len(query.get(k, [])) == 1 and query[k][0] for k in ('aibotid', 'str_aibotid')))
    except ValueError:
        return False


def inspect_desktop(cfg, ax, *, expand=False):
    engine = Renewal(cfg, ax)
    native, engine.app = ax.application()
    with exposed_tree(ax, engine.app) if expand else nullcontext(None) as exposure:
        result = snapshot(engine, native, cfg, ax)
        if exposure is not None:
            result['native_tree_exposure'] = exposure
    return result


def native_controls(engine, root):
    """Inspect native robot-page scroll content while excluding web/chat editors."""
    stack, total = [(root, 0)], 0
    while stack:
        node, depth = stack.pop()
        total += 1
        if total > 5000 or depth > 40:
            from keeper_common import KeeperError
            raise KeeperError('tree_incomplete', 'Native inspection tree exceeds limits')
        if engine.ax.ax_get(node, 'AXRole') in {'AXWebArea', 'AXTable', 'AXTextArea'}:
            continue
        yield node
        stack.extend((c, depth + 1) for c in engine.ax.ax_get(node, 'AXChildren') or [])


def bot_directory(engine, window, cfg):
    """Recognize the 5.0.13 contacts landing page, not management cards.

    Only fixed native icon/heading pairs qualify an outline. Return counts and
    candidate geometry, never names or other contact text. Visible rows cannot
    establish a complete directory, Bot identity, organization or private chat.
    """
    ax = engine.ax
    directories = []
    for outline in native_controls(engine, window):
        if ax.ax_get(outline, 'AXRole') != 'AXOutline':
            continue
        rows = [n for n in ax.ax_get(outline, 'AXChildren') or []
                if ax.ax_get(n, 'AXRole') == 'AXRow']
        parsed = []
        for row in rows:
            nodes = list(engine.walk(row))
            icons = {str(ax.ax_get(n, 'AXDescription') or '') for n in nodes
                     if ax.ax_get(n, 'AXRole') == 'AXImage'}
            names = [engine.text(n) for n in nodes
                     if ax.ax_get(n, 'AXRole') == 'AXTextArea' and engine.text(n)]
            parsed.append((row, icons, names))
        headings = [i for i, (_, icons, names) in enumerate(parsed)
                    if names == ['智能机器人'] and icons & {
                        'avatar starred bot selected', 'avatar starred bot'}]
        if len(headings) != 1:
            continue
        count, candidates = 0, []
        for row, icons, names in parsed[headings[0] + 1:]:
            if icons & {'avatar b2b tree', 'avatar company', 'icon new friend'}:
                break
            if 'icon bot' not in icons or len(names) != 1:
                continue
            bounds = ax.frame(row)
            if not engine.contains(ax.frame(outline), bounds):
                continue
            count += 1
            if names == [cfg['bot_chat_name']]:
                candidates.append({'bounds': bounds, 'actions': ax.action_names(row)})
        directories.append({'kind': 'contacts_bot_directory', 'bounds': ax.frame(outline),
                            'visible_bot_rows': count, 'configured_name_candidates': candidates,
                            'list_complete': False, 'target_identity_verified': False})
    return directories


def snapshot(engine, native, cfg, ax):
    result = {'ok': True, 'mode': 'desktop-inspection', 'renewal_verified': False,
              'navigation_performed': False, 'authorization_changed': False,
              'client_version': ax.client_version(native), 'windows': [],
              'visible_organization_menu': [{'name': r[0], 'selected': r[1]} for r in menu_rows(engine)]}
    for number, window in enumerate(ax.ax_get(engine.app, 'AXWindows') or []):
        entry = {'window_index': number, 'bounds': ax.frame(window),
                 'main_window_sidebar_present': bool(sidebar_rows(engine, window)),
                 'native_controls': [], 'official_permission_pages': [],
                 'bot_directories': bot_directory(engine, window, cfg)}
        result['windows'].append(entry)
        for node in native_controls(engine, window):
            for match in native_labels(ax, node):
                entry['native_controls'].append({**match, 'role': ax.ax_get(node, 'AXRole'),
                                                'bounds': ax.frame(node), 'actions': ax.action_names(node)})
        for node in engine.walk(window):
            if ax.ax_get(node, 'AXRole') != 'AXWebArea':
                continue
            values = [ax.ax_get(node, k) for k in ('AXURL', 'AXValue', 'AXTitle')]
            values = [v for v in values if official_page(v)]
            if not values:
                continue
            page = {'matches_configured_bot': any(target_url(v, cfg) for v in values),
                    'bounds': ax.frame(node), 'permission_controls': []}
            entry['official_permission_pages'].append(page)
            for control in engine.walk(node):
                text = engine.text(control)
                if text in PERMISSION_LABELS:
                    page['permission_controls'].append({'label': text, 'role': ax.ax_get(control, 'AXRole'),
                                                        'actions': ax.action_names(control)})
            if page['matches_configured_bot']:
                rows = engine.read_rows(window)
                page['target_rows'] = {name: {'status': row['status'],
                    'expiry': row['expiry'].isoformat(timespec='minutes') if row['expiry'] else None}
                    for name, row in rows.items()}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--expose-native-tree', action='store_true',
                   help='Temporarily expand the advertised native AX tree, then restore its original flag')
    args = p.parse_args()
    try:
        cfg = load_config(args.config)
        import keeper_ax as ax
        result = inspect_desktop(cfg, ax, expand=args.expose_native_tree)
        code = 0
    except Exception as exc:
        result, code = emit_error(exc)
        if getattr(exc, 'ax_exposure_cleanup_failed', False):
            result['native_tree_restore_failed'] = True
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
