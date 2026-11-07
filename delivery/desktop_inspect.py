#!/usr/bin/env python3
"""Observe native controls and official permission pages; never navigate or click.

This is a diagnostic snapshot, safe to request without claiming desktop ownership.
No raw URLs, Bot IDs, conversation text, clipboard or credential files are emitted.
"""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keeper_common import emit_error, load_config
from keeper_navigation import chrome, label
from keeper_organization import menu_rows
from renew import Renewal, target_url

NATIVE_LABELS = {'消息', '机器人', '机器人详情', '管理', '去管理', '去使用', '详情', '可使用权限',
                 '查找聊天记录', '关闭聊天记录'}
PERMISSION_LABELS = {'授权', '已授权', '取消授权', '确认', '确定', '同意', '重新授权'}


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


def inspect_desktop(cfg, ax):
    engine = Renewal(cfg, ax)
    native, engine.app = ax.application()
    result = {'ok': True, 'mode': 'desktop-inspection', 'renewal_verified': False,
              'navigation_performed': False, 'authorization_changed': False,
              'client_version': ax.client_version(native), 'windows': [],
              'visible_organization_menu': [{'name': r[0], 'selected': r[1]} for r in menu_rows(engine)]}
    for number, window in enumerate(ax.ax_get(engine.app, 'AXWindows') or []):
        entry = {'window_index': number, 'bounds': ax.frame(window),
                 'native_controls': [], 'official_permission_pages': []}
        result['windows'].append(entry)
        for node in chrome(engine, window):
            text = label(engine, node)
            if text in NATIVE_LABELS:
                entry['native_controls'].append({'label': text, 'role': ax.ax_get(node, 'AXRole'),
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
    args = p.parse_args()
    try:
        cfg = load_config(args.config)
        import keeper_ax as ax
        result = inspect_desktop(cfg, ax)
        code = 0
    except Exception as exc:
        result, code = emit_error(exc)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
