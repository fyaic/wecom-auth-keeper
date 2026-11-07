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

    def test_embedded_management_modal_never_closes_main_wecom_window(self):
        ax, _, _ = self.setup_window()
        rows = [node('AXRow', _frame=(0, 100 + i * 56, 60, 56)) for i in range(9)]
        ax.window['AXChildren'].insert(0, node('AXTable', children=rows, _frame=(0, 100, 60, 504)))
        with patch.object(ax, 'ax_perform') as action:
            with self.assertRaises(KeeperError) as caught:
                self.engine(ax).close_window()
        self.assertEqual(caught.exception.code, 'embedded_page_close_unavailable')
        action.assert_not_called()

    def test_rejected_or_ineffective_close_is_failure(self):
        for status in (0, -1):
            ax, _, _ = self.setup_window()
            with patch.object(ax, 'ax_perform', return_value=status):
                with self.assertRaises(KeeperError): self.engine(ax).close_window()

    def setup_sheet(self):
        ax, _, other = self.setup_window()
        ax.client_version = lambda _: '5.0.13'
        ax.action_names = lambda n: ['AXPress'] if n.get('AXRole') == 'AXButton' else []
        ax.page['_frame'] = (100, 100, 720, 640)
        heading = node('AXStaticText', '可使用权限', _frame=(148, 129, 80, 18))
        close = node('AXButton', _frame=(744, 124, 28, 28))
        ax.page['AXChildren'] = [heading, close, node('AXButton', '授权', _frame=(640, 250, 90, 32))]
        sheet = node('AXSheet', children=[ax.page], _frame=ax.page['_frame'])
        ax.page['AXParent'] = sheet
        sheet['AXParent'] = ax.window
        rows = [node('AXRow', _frame=(0, 100 + i * 56, 60, 56)) for i in range(9)]
        ax.window['AXChildren'] = [node('AXTable', children=rows, _frame=(0, 100, 60, 504)), sheet]
        return ax, sheet, close, heading, other

    def test_verified_sheet_closes_without_main_window_or_authorization_action(self):
        ax, sheet, button, _, other = self.setup_sheet()
        def close(n, action):
            self.assertIs(n, button)
            self.assertEqual(action, 'AXPress')
            ax.window['AXChildren'].remove(sheet)
            return 0
        with patch.object(ax, 'ax_perform', side_effect=close):
            result, code = self.engine(ax).close_window()
        self.assertEqual((result['closed_kind'], code), ('embedded-sheet', 0))
        self.assertEqual(ax.app['AXWindows'], [ax.window, other])
        self.assertEqual(ax.clicks, [])

    def test_unverified_sheet_header_never_falls_back_to_main_window_close(self):
        for change in ('version', 'title', 'named_button', 'geometry', 'extra_button', 'extra_page', 'ancestry'):
            with self.subTest(change=change):
                ax, sheet, button, heading, _ = self.setup_sheet()
                if change == 'version': ax.client_version = lambda _: '5.0.14'
                if change == 'title': heading['AXTitle'] = 'Other page'
                if change == 'named_button': button['AXTitle'] = '授权'
                if change == 'geometry': button['_frame'] = (740, 180, 28, 28)
                if change == 'extra_button': ax.page['AXChildren'].append(node('AXButton', _frame=(700, 124, 28, 28)))
                if change == 'extra_page': sheet['AXChildren'].append(node('AXWebArea'))
                if change == 'ancestry': ax.page.pop('AXParent')
                with patch.object(ax, 'ax_perform') as action:
                    with self.assertRaises(KeeperError) as caught: self.engine(ax).close_window()
                self.assertEqual(caught.exception.code, 'embedded_page_close_unavailable')
                action.assert_not_called()

    def test_ineffective_sheet_press_cannot_report_cleanup_success(self):
        ax, _, _, _, _ = self.setup_sheet()
        with patch.object(ax, 'ax_perform', return_value=0):
            with self.assertRaises(KeeperError) as caught: self.engine(ax).close_window()
        self.assertEqual(caught.exception.code, 'window_close_failed')

    def test_sheet_ancestry_protects_main_window_even_when_sidebar_is_hidden(self):
        ax, sheet, button, _, _ = self.setup_sheet()
        ax.window['AXChildren'] = [sheet, node('AXGroup')]
        def close(n, action):
            self.assertIs(n, button)
            ax.window['AXChildren'].remove(sheet)
            return 0
        with patch.object(ax, 'ax_perform', side_effect=close):
            result, _ = self.engine(ax).close_window()
        self.assertEqual(result['closed_kind'], 'embedded-sheet')
        self.assertIn(ax.window, ax.app['AXWindows'])

    def test_missing_page_url_during_sheet_rebuild_does_not_count_as_closed(self):
        ax, _, _, _, _ = self.setup_sheet()
        def incomplete(n, action):
            ax.page.pop('AXURL')
            return 0
        with patch.object(ax, 'ax_perform', side_effect=incomplete):
            with self.assertRaises(KeeperError) as caught: self.engine(ax).close_window()
        self.assertEqual(caught.exception.code, 'window_close_failed')
