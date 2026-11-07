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
    native, original, failure = None, None, None
    result = {'ok': False, 'mode': 'discovery', 'renewal_verified': False,
              'organizations': [], 'verified_organizations': [],
              'stage': 'enumerating_organizations', 'cleanup': {'attempted': False}}
    try:
        native, engine.app = ax.application()
        organizations = list_organizations(engine, native)
        original = next(r['name'] for r in organizations if r['selected'])
        result['enumerated_organizations'] = [r['name'] for r in organizations]
        for organization in organizations:
            name = organization['name']
            engine.cfg.update(organization_navigation='sidebar-5.0.13', organization_selector_name=name)
            entry = {'organization': name, 'chat_name_matched': False, 'link_identity_verified': False}
            result['organizations'].append(entry)
            result.update(stage='selecting_organization', current_candidate=name)
            ensure_organization(engine, native)
            result['stage'] = 'finding_chat_entry'
            try:
                window, _ = open_chat(engine, native)
                entry['chat_name_matched'] = True
                if not engine.visible_links([window]):
                    open_chat_history(engine, native)
                entry['link_identity_verified'] = bool(engine.visible_links([window]))
            except KeeperError as exc:
                # A missing candidate/link is expected during discovery. Focus,
                # identity or unknown layout failures must stop, not be ignored.
                if exc.code not in {'navigation_target_not_found', 'link_not_visible'}:
                    raise
                entry['error'] = exc.code
        verified = [r['organization'] for r in result['organizations'] if r['link_identity_verified']]
        result.update(ok=True, stage='completed', verified_organizations=verified,
                      status='unique_verified_entry' if len(verified) == 1 else 'identity_review_required')
    except Exception as exc:
        failure = exc
    finally:
        if original is not None:
            engine.cfg.update(organization_navigation='sidebar-5.0.13', organization_selector_name=original)
            result['cleanup'] = {'attempted': True, 'ok': False}
            try:
                ensure_organization(engine, native)
                result['cleanup']['ok'] = True
            except Exception as exc:
                error, _ = emit_error(exc)
                result['cleanup']['error'] = error['error']
                if failure is None:
                    failure = KeeperError('discovery_restore_failed', 'Could not restore the original organization')
    result['verified_organizations'] = [r['organization'] for r in result['organizations']
                                        if r['link_identity_verified']]
    if failure is not None:
        result['ok'] = False
        # Keep the original failure, partial coverage and cleanup failure distinct.
        # Only organization names and fixed status fields are retained, never AX/URLs.
        if not isinstance(failure, KeeperError):
            failure = KeeperError('discovery_failed', 'Organization discovery failed')
        failure.discovery = result
        raise failure
    return result


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
        if isinstance(exc, KeeperError) and hasattr(exc, 'discovery'):
            result['discovery'] = exc.discovery
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
