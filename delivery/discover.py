#!/usr/bin/env python3
"""Read-only organization/chat discovery. Never sends or changes permissions."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keeper_common import KeeperError, emit_error, gui_lock_path, load_config, process_lock
from keeper_navigation import open_chat, open_chat_history
from keeper_organization import ensure_organization, list_organizations
from renew import Renewal, monitor_guard


def discover(cfg, ax):
    engine = Renewal(dict(cfg), ax)
    native, engine.app = ax.application()
    organizations = list_organizations(engine, native)
    original = next(r['name'] for r in organizations if r['selected'])
    results = []
    try:
        for organization in organizations:
            name = organization['name']
            engine.cfg.update(organization_navigation='sidebar-5.0.13', organization_selector_name=name)
            result = {'organization': name, 'chat_name_matched': False, 'link_identity_verified': False}
            results.append(result)
            ensure_organization(engine, native)
            try:
                window, _ = open_chat(engine, native)
                result['chat_name_matched'] = True
                if not engine.visible_links([window]):
                    open_chat_history(engine, native)
                result['link_identity_verified'] = bool(engine.visible_links([window]))
            except KeeperError as exc:
                # A missing candidate/link is expected during discovery. Focus,
                # identity or unknown layout failures must stop, not be ignored.
                if exc.code not in {'navigation_target_not_found', 'link_not_visible'}:
                    raise
                result['error'] = exc.code
        verified = [r['organization'] for r in results if r['link_identity_verified']]
        return {'ok': True, 'mode': 'discovery', 'renewal_verified': False,
                'organizations': results, 'verified_organizations': verified,
                'status': 'unique_verified_entry' if len(verified) == 1 else 'identity_review_required'}
    finally:
        engine.cfg.update(organization_navigation='sidebar-5.0.13', organization_selector_name=original)
        ensure_organization(engine, native)


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    args = p.parse_args()
    try:
        cfg = load_config(args.config)
        import keeper_ax as ax
        with process_lock(gui_lock_path(), cfg['lock_wait']), monitor_guard(cfg):
            result = discover(cfg, ax)
        code = 0
    except Exception as exc:
        result, code = emit_error(exc)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
