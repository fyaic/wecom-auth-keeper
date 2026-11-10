#!/usr/bin/env python3
"""Establish explicitly approved first-use scopes; never revoke a healthy grant.

Installer-only action. Requires the user's approval for every configured scope;
not a renewal success or entry receipt. The regular service never calls it.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from keeper_accessibility import exposed_tree
from keeper_common import KeeperError,emit_error,gui_lock_path,load_config,process_lock
from delivery.verify_entry import verify_cli
from renew import Renewal


def grant(cfg, ax, *, engine=None):
    engine=engine or Renewal(cfg,ax)
    result=None
    failure=None
    try:
        result,code=engine.run('renew')
        result.update(mode='initial-grant',renewal_verified=False,
                      scope_allowlist=list(cfg['target_rows']))
        return result,code
    except Exception as exc:
        failure=exc
        raise
    finally:
        try:
            closed,_=engine.close_window()
            if result is not None:
                result['cleanup']={'ok':True,'closed':closed['closed']}
        except Exception:
            if failure is not None:
                failure.initial_grant_cleanup_failed=True
            else:
                raise KeeperError('initial_grant_cleanup_failed','Could not close the verified permission page') from None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True)
    p.add_argument('--scopes-confirmed',required=True,action='store_true',
                   help='User explicitly approved the exact configured first-use scopes')
    args=p.parse_args()
    try:
        cfg=load_config(args.config)
        verify_cli(cfg)
        import keeper_ax as ax
        with process_lock(gui_lock_path(),cfg['lock_wait']):
            _,app=ax.application()
            with exposed_tree(ax,app):
                result,code=grant(cfg,ax)
    except Exception as exc:
        result,code=emit_error(exc)
        if getattr(exc,'initial_grant_cleanup_failed',False):
            result['cleanup']={'ok':False}
    print(json.dumps(result,ensure_ascii=False))
    return code

if __name__=='__main__':raise SystemExit(main())
