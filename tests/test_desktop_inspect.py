import json
from unittest.mock import patch

from test_delivery import module
from test_keeper import FakeAX, Fixture, node
from test_accessibility import ExposureAdapter

inspection = module('desktop_inspect')


class DesktopInspectionTests(Fixture):
    def adapter(self):
        ax = FakeAX(self.cfg)
        ax.client_version = lambda _: '5.0.13'
        ax.action_names = lambda n: ['AXPress'] if n.get('AXRole') == 'AXButton' else []
        def forbidden(*args):
            raise AssertionError('inspection must not act on the desktop')
        ax.click = ax.activate = ax.ax_perform = forbidden
        return ax

    def test_snapshot_never_clicks_or_coordinates_bridge_and_omits_private_text(self):
        self.cfg.update(bridge_monitor=True, bridge_url='http://localhost:23392')
        ax = self.adapter()
        ax.window['AXChildren'].append(node('AXTable', children=[node('AXStaticText', 'private conversation body')]))
        with patch('renew.bridge_request', side_effect=AssertionError('no Bridge calls')):
            result = inspection.inspect_desktop(self.cfg, ax)
        page = result['windows'][0]['official_permission_pages'][0]
        self.assertTrue(page['matches_configured_bot'])
        self.assertEqual(set(page['target_rows']), set(self.cfg['target_rows']))
        self.assertFalse(result['navigation_performed'])
        self.assertFalse(result['authorization_changed'])
        self.assertFalse(result['renewal_verified'])
        encoded = json.dumps(result)
        for forbidden in ('private conversation body', 'https://', 'str_aibotid', 'fixture'):
            self.assertNotIn(forbidden, encoded)

    def test_other_bot_page_is_a_mismatch_not_a_target_or_authorization(self):
        ax = self.adapter()
        ax.page['AXURL'] = ax.page['AXURL'].replace('str_aibotid=fixture', 'str_aibotid=other-private-id')
        page = inspection.inspect_desktop(self.cfg, ax)['windows'][0]['official_permission_pages'][0]
        self.assertFalse(page['matches_configured_bot'])
        self.assertNotIn('target_rows', page)
        self.assertNotIn('other-private-id', json.dumps(page))

    def test_expanded_snapshot_restores_flag_and_reads_native_robot_landmarks(self):
        ax = self.adapter()
        exposure = ExposureAdapter()
        original_get = ax.ax_get
        ax.ax_get = lambda n, k: exposure.value if k == 'AXEnhancedUserInterface' else original_get(n, k)
        ax.ax_set, ax.ax_settable = exposure.ax_set, exposure.ax_settable
        ax.window['AXChildren'].append(node('AXScrollArea', children=[node('AXImage', '管理机器人')]))
        result = inspection.inspect_desktop(self.cfg, ax, expand=True)
        self.assertTrue(result['native_tree_exposure']['restored'])
        self.assertFalse(exposure.value)
        self.assertIn('管理机器人', [c['label'] for c in result['windows'][0]['native_controls']])

    def test_foreign_or_ambiguous_permission_urls_are_not_official_pages(self):
        valid = 'https://work.weixin.qq.com/ai/aiHelper/authorizationList?aibotid=123&str_aibotid=fixture'
        for url in (valid.replace('https:', 'http:'), valid.replace('work.weixin.qq.com', 'work.weixin.qq.com.evil.example'),
                    valid.replace('https://', 'https://user@'), valid + '&aibotid=456', valid.replace('aibotid=123', 'aibotid=')):
            self.assertFalse(inspection.official_page(url))
        self.assertTrue(inspection.official_page(valid))
