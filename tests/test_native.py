"""Real native value conversion; no actual application reads or GUI clicks."""
import importlib.util
import sys
import unittest
from unittest.mock import Mock, patch
from keeper_common import KeeperError, emit_error


@unittest.skipUnless(sys.platform == "darwin" and importlib.util.find_spec("ApplicationServices"), "Native dependencies unavailable")
class NativeTests(unittest.TestCase):
    def test_untrusted_process_returns_fixed_code_before_application_discovery(self):
        import keeper_ax
        with patch.object(keeper_ax, "AXIsProcessTrusted", return_value=False), \
             patch.object(keeper_ax, "NSWorkspace") as workspace, \
             patch.object(keeper_ax, "AXUIElementCreateApplication") as create:
            with self.assertRaises(KeeperError) as caught:
                keeper_ax.application()
        self.assertEqual(caught.exception.code, 'accessibility_permission_unavailable')
        payload, code = emit_error(caught.exception)
        self.assertEqual(code, 3)
        self.assertEqual(payload['error'], 'accessibility_permission_unavailable')
        self.assertFalse(payload['ok'])
        workspace.sharedWorkspace.assert_not_called()
        create.assert_not_called()

    def test_absent_application_is_not_misreported_as_missing_accessibility_permission(self):
        import keeper_ax
        with patch.object(keeper_ax, "AXIsProcessTrusted", return_value=True), \
             patch.object(keeper_ax, "NSWorkspace") as workspace:
            workspace.sharedWorkspace.return_value.runningApplications.return_value = []
            with self.assertRaises(KeeperError) as caught:
                keeper_ax.application()
        self.assertEqual(caught.exception.code, 'wecom_not_running')

    def test_running_application_without_accessible_window_has_distinct_code(self):
        import keeper_ax
        app = Mock()
        app.bundleIdentifier.return_value = "com.tencent.WeWorkMac"
        app.processIdentifier.return_value = 123
        with patch.object(keeper_ax, "AXIsProcessTrusted", return_value=True), \
             patch.object(keeper_ax, "NSWorkspace") as workspace, \
             patch.object(keeper_ax, "AXUIElementCreateApplication", return_value=object()), \
             patch.object(keeper_ax, "ax_get", return_value=None):
            workspace.sharedWorkspace.return_value.runningApplications.return_value = [app]
            with self.assertRaises(KeeperError) as caught:
                keeper_ax.application()
        self.assertEqual(caught.exception.code, 'wecom_window_unavailable')

    def test_multiple_windowed_instances_are_rejected_without_private_process_details(self):
        import keeper_ax
        apps = [Mock(), Mock()]
        for pid, app in enumerate(apps):
            app.bundleIdentifier.return_value = "com.tencent.WeWorkMac"
            app.processIdentifier.return_value = pid + 123
        with patch.object(keeper_ax, "AXIsProcessTrusted", return_value=True), \
             patch.object(keeper_ax, "NSWorkspace") as workspace, \
             patch.object(keeper_ax, "AXUIElementCreateApplication", return_value=object()), \
             patch.object(keeper_ax, "ax_get", return_value=[object()]):
            workspace.sharedWorkspace.return_value.runningApplications.return_value = apps
            with self.assertRaises(KeeperError) as caught:
                keeper_ax.application()
        payload, code = emit_error(caught.exception)
        self.assertEqual(caught.exception.code, 'wecom_multiple_instances')
        self.assertEqual(code, 2)
        self.assertNotIn('123', str(payload))
        self.assertNotIn('124', str(payload))

    def test_negative_ax_value_geometry(self):
        import keeper_ax
        from ApplicationServices import AXValueCreate, kAXValueCGPointType, kAXValueCGSizeType
        from Quartz import CGPoint, CGSize
        attributes = {"AXPosition": AXValueCreate(kAXValueCGPointType, CGPoint(-100, -200)),
                      "AXSize": AXValueCreate(kAXValueCGSizeType, CGSize(120, 20))}
        with patch.object(keeper_ax, "ax_get", side_effect=lambda e,k: attributes[k]):
            self.assertEqual(keeper_ax.frame(object()), (-100, -200, 120, 20))

    def test_calls_process_identifier_method(self):
        import keeper_ax
        app = Mock()
        app.bundleIdentifier.return_value = "com.tencent.WeWorkMac"
        app.processIdentifier.return_value = 123
        with patch.object(keeper_ax, "AXIsProcessTrusted", return_value=True), \
             patch.object(keeper_ax, "NSWorkspace") as workspace, \
             patch.object(keeper_ax, "AXUIElementCreateApplication") as create, \
             patch.object(keeper_ax, "ax_get", return_value=[object()]):
            workspace.sharedWorkspace.return_value.runningApplications.return_value = [app]
            keeper_ax.application()
        self.assertTrue(all(call.args == (123,) for call in create.call_args_list))

    def test_offscreen_control_cannot_click(self):
        import keeper_ax
        with patch.object(keeper_ax, "frame", side_effect=[(2000,2000,100,20),(0,0,900,800)]), \
             patch.object(keeper_ax, "AXUIElementCopyActionNames", return_value=(0, [])), \
             patch.object(keeper_ax, "ax_perform") as press, \
             patch.object(keeper_ax, "CGEventPost") as mouse:
            with self.assertRaises(RuntimeError):
                keeper_ax.click(object(), object())
        press.assert_not_called()
        mouse.assert_not_called()

    def test_windowless_duplicate_process_is_ignored(self):
        import keeper_ax
        live, empty = Mock(), Mock()
        for app, pid in [(live, 123), (empty, 456)]:
            app.bundleIdentifier.return_value = "com.tencent.WeWorkMac"
            app.processIdentifier.return_value = pid
        with patch.object(keeper_ax, "AXIsProcessTrusted", return_value=True), \
             patch.object(keeper_ax, "NSWorkspace") as workspace, \
             patch.object(keeper_ax, "AXUIElementCreateApplication", side_effect=lambda pid: pid), \
             patch.object(keeper_ax, "ax_get", side_effect=lambda app, attr: [1] if app == 123 else []):
            workspace.sharedWorkspace.return_value.runningApplications.return_value = [live, empty]
            self.assertEqual(keeper_ax.application(), (live, 123))

    def test_scrolls_and_rechecks_geometry_before_press(self):
        import keeper_ax
        element, viewport = object(), object()
        with patch.object(keeper_ax, "frame", side_effect=[(20, 1000, 50, 20), (0, 0, 560, 560), (20, 250, 50, 20)]), \
             patch.object(keeper_ax, "AXUIElementCopyActionNames", return_value=(0, ['AXScrollToVisible', 'AXPress'])), \
             patch.object(keeper_ax, "ax_perform", return_value=0) as action, \
             patch.object(keeper_ax, "CGEventPost") as mouse:
            keeper_ax.click(element, viewport)
            self.assertEqual([c.args[1] for c in action.call_args_list], ['AXScrollToVisible', 'AXPress'])
            mouse.assert_not_called()
