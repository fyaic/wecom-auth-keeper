"""Scoped native AX-tree exposure, separate from system Accessibility permission."""
from contextlib import contextmanager
import time

from keeper_common import KeeperError

ATTRIBUTE = 'AXEnhancedUserInterface'


@contextmanager
def exposed_tree(ax, app, *, clock=time.monotonic, sleep=time.sleep):
    """Request an advertised native tree and restore the original flag on exit.

    WeCom 5.0.13 can return an AX setter error while applying this flag. Readback,
    not a successful setter return alone, establishes the actual state. No app
    activation, keyboard/mouse input, TCC changes or Bridge requests occur here.
    """
    original = ax.ax_get(app, ATTRIBUTE)
    if type(original) not in (bool, int) or original not in (False, True):
        raise KeeperError('ax_exposure_unavailable', 'Native accessibility expansion is unavailable')
    original = bool(original)
    report = {'original': original, 'changed': False, 'restored': False}
    if original:
        report['restored'] = True  # Already enabled; this scope owns no change.
        yield report
        return
    if not ax.ax_settable(app, ATTRIBUTE):
        raise KeeperError('ax_exposure_unavailable', 'Native accessibility expansion is not writable')

    def wait_value(expected):
        deadline = clock() + 2
        while True:
            value = ax.ax_get(app, ATTRIBUTE)
            if type(value) in (bool, int) and value == expected:
                return True
            if clock() >= deadline:
                return False
            sleep(.05)

    failure = None
    try:
        report['enable_result'] = ax.ax_set(app, ATTRIBUTE, True)
        if not wait_value(True):
            raise KeeperError('ax_exposure_failed', 'Native accessibility expansion did not take effect')
        report['changed'] = True
        # The advertised flag changes before WeCom rebuilds its native page tree.
        sleep(1)
        yield report
    except BaseException as exc:
        failure = exc
        raise
    finally:
        # A failed setter may have changed the flag, so restoration is unconditional.
        try:
            report['restore_result'] = ax.ax_set(app, ATTRIBUTE, original)
            report['restored'] = wait_value(original)
        except Exception:
            report['restored'] = False
        if not report['restored']:
            if failure is not None:
                failure.ax_exposure_cleanup_failed = True
            else:
                raise KeeperError('ax_exposure_restore_failed', 'Native accessibility expansion could not be restored')

