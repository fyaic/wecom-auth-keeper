from unittest.mock import patch
import json
from pathlib import Path

from test_keeper import Fixture, FakeAX, node
from keeper_common import KeeperError, atomic_json


class CleanupTests(Fixture):
    def setup_window(self):
        ax = FakeAX(self.cfg)
        button = node('AXButton', AXSubrole='AXCloseButton')
        ax.window['AXCloseButton'] = button
        other = node('AXWindow', 'unrelated')
        ax.app['AXWindows'].append(other)
        def close(element, action):
            self.assertIs(element, button)
            self.assertEqual(action, 'AXPress')
            ax.app['AXWindows'].remove(ax.window)
            return 0
        return ax, close, other

    def test_closes_only_target_and_preserves_state_and_pending(self):
        ax, close, other = self.setup_window()
        engine = self.engine(ax)
        atomic_json(self.cfg['state_file'], {'health': 'preserve'})
        atomic_json(engine.journal, {'recovery': 'preserve'})
        with patch.object(ax, 'ax_perform', side_effect=close):
            result, code = engine.close_window()
        self.assertEqual((result['closed'], code), (True, 0))
        self.assertEqual(ax.app['AXWindows'], [other])
        self.assertEqual(json.loads(Path(self.cfg['state_file']).read_text()), {'health': 'preserve'})
        self.assertTrue(engine.journal.exists())
        self.assertEqual(ax.clicks, [])

    def test_missing_or_wrong_target_is_noop_without_navigation(self):
        ax, _, _ = self.setup_window()
        ax.page['AXURL'] = ax.page['AXURL'].replace('123', '999')
        with patch.object(ax, 'ax_perform') as action, patch.object(ax, 'activate') as activate:
            self.assertFalse(self.engine(ax).close_window()[0]['closed'])
        action.assert_not_called()
        activate.assert_not_called()

    def test_ambiguous_windows_refuse_close(self):
        ax, _, _ = self.setup_window()
        ax.app['AXWindows'].append(ax.window)
        with patch.object(ax, 'ax_perform') as action:
            with self.assertRaisesRegex(KeeperError, 'duplicate'):
                self.engine(ax).close_window()
        action.assert_not_called()

    def test_multiple_web_pages_refuse_close(self):
        ax, _, _ = self.setup_window()
        ax.window['AXChildren'].append(node('AXWebArea', AXURL='https://example.org'))
        with patch.object(ax, 'ax_perform') as action:
            with self.assertRaises(KeeperError): self.engine(ax).close_window()
        action.assert_not_called()

    def test_missing_native_close_button_refuses_keyboard_fallback(self):
        ax, _, _ = self.setup_window()
        del ax.window['AXCloseButton']
        with patch.object(ax, 'ax_perform') as action:
            with self.assertRaises(KeeperError): self.engine(ax).close_window()
        action.assert_not_called()

    def test_rejected_or_ineffective_close_is_failure(self):
        for status in (0, -1):
            ax, _, _ = self.setup_window()
            with patch.object(ax, 'ax_perform', return_value=status):
                with self.assertRaises(KeeperError): self.engine(ax).close_window()
