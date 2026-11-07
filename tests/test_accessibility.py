import unittest

from keeper_accessibility import ATTRIBUTE, exposed_tree
from keeper_common import KeeperError


class ExposureAdapter:
    def __init__(self, value=False, *, writable=True, applies=True, restore=True):
        self.value, self.writable, self.applies, self.restore = value, writable, applies, restore
        self.calls, self.now = [], 0

    def ax_get(self, app, key):
        assert key == ATTRIBUTE
        return self.value

    def ax_settable(self, app, key):
        return self.writable

    def ax_set(self, app, key, value):
        assert key == ATTRIBUTE
        self.calls.append(value)
        if (value and self.applies) or (not value and self.restore):
            self.value = value
        return -25208  # Reproduced on the remote WeCom 5.0.13, despite applied state.

    def clock(self):
        self.now += 1
        return self.now

    def context(self):
        return exposed_tree(self, object(), clock=self.clock, sleep=lambda _: None)


class AccessibilityExposureTests(unittest.TestCase):
    def test_applied_state_is_read_back_and_original_is_restored_on_body_failure(self):
        ax = ExposureAdapter()
        with self.assertRaisesRegex(RuntimeError, 'navigation failed'):
            with ax.context() as evidence:
                self.assertTrue(ax.value)
                raise RuntimeError('navigation failed')
        self.assertFalse(ax.value)
        self.assertTrue(evidence['restored'])
        self.assertEqual(ax.calls, [True, False])

    def test_successful_scope_reports_actual_restoration_after_exit(self):
        ax = ExposureAdapter()
        with ax.context() as evidence:
            self.assertFalse(evidence['restored'])
        self.assertTrue(evidence['restored'])

    def test_preexisting_enabled_state_is_not_disabled(self):
        ax = ExposureAdapter(True)
        with ax.context() as evidence:
            self.assertFalse(evidence['changed'])
        self.assertEqual(ax.calls, [])
        self.assertTrue(ax.value)

    def test_unavailable_or_not_settable_does_not_attempt_change(self):
        for ax in (ExposureAdapter(None), ExposureAdapter('true'), ExposureAdapter(writable=False)):
            with self.assertRaises(KeeperError) as caught:
                with ax.context():
                    self.fail('unsupported tree must not be used')
            self.assertEqual(caught.exception.code, 'ax_exposure_unavailable')
            self.assertEqual(ax.calls, [])

    def test_unapplied_enable_never_proceeds_and_still_restores(self):
        ax = ExposureAdapter(applies=False)
        with self.assertRaises(KeeperError) as caught:
            with ax.context():
                self.fail('unexposed tree must not be used')
        self.assertEqual(caught.exception.code, 'ax_exposure_failed')
        self.assertEqual(ax.calls, [True, False])

    def test_restore_failure_prevents_success_but_does_not_mask_primary_failure(self):
        ax = ExposureAdapter(restore=False)
        with self.assertRaises(KeeperError) as caught:
            with ax.context():
                pass
        self.assertEqual(caught.exception.code, 'ax_exposure_restore_failed')
        ax = ExposureAdapter(restore=False)
        original = KeeperError('identity_unverified', 'Target changed')
        with self.assertRaises(KeeperError) as caught:
            with ax.context():
                raise original
        self.assertIs(caught.exception, original)
        self.assertTrue(original.ax_exposure_cleanup_failed)

    def test_setter_exception_after_apply_also_restores(self):
        ax = ExposureAdapter()
        original_set = ax.ax_set
        def broken(app, key, value):
            original_set(app, key, value)
            if value:
                raise RuntimeError('setter failed after changing state')
        ax.ax_set = broken
        with self.assertRaises(RuntimeError):
            with ax.context():
                self.fail('setter raised')
        self.assertFalse(ax.value)

