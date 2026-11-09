import json
from unittest.mock import patch

from test_delivery import module
from test_keeper import FakeAX, Fixture, node
from test_accessibility import ExposureAdapter

inspection = module('desktop_inspect')


class DesktopInspectionTests(Fixture):
    def test_creator_error_is_reported_without_private_body_or_success_rows(self):
        ax = self.adapter()
        ax.page['AXChildren'] = [node('AXStaticText',
            '暂无法授权，仅限机器人创建者可进行授权。请联系机器人创建者 private-name 进行处理。')]
        for cfg in (self.cfg, None):
            result = inspection.inspect_desktop(cfg, ax)
            page = result['windows'][0]['official_permission_pages'][0]
            self.assertEqual(page['blocking_error'], 'authorization_creator_required')
            self.assertNotIn('target_rows', page)
            self.assertNotIn('private-name', json.dumps(result))
            self.assertFalse(result['renewal_verified'])

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

    def test_page_lookup_does_not_walk_chat_history_or_unrelated_web_content(self):
        ax=self.adapter()
        trap=node('AXGroup', 'private loaded content')
        unrelated=node('AXWebArea', children=[trap],AXURL='https://example.com/')
        ax.window['AXChildren'] += [unrelated,node('AXTable',children=[trap])]
        get=ax.ax_get
        def guarded(n,k):
            if n is trap:raise AssertionError('must not traverse chat/document bodies')
            return get(n,k)
        ax.ax_get=guarded
        result=inspection.inspect_desktop(None,ax)
        self.assertEqual(len(result['windows'][0]['official_permission_pages']),1)

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

    def test_composite_native_card_reports_only_allowlisted_semantics_and_sources(self):
        ax = self.adapter()
        ax.window['AXChildren'].append(node('AXGroup', 'private bot name',
            AXDescription='可使用权限\nprivate permission description\n授权消息',
            AXHelp='可使用权限'))
        result = inspection.inspect_desktop(self.cfg, ax)
        controls = result['windows'][0]['native_controls']
        card = next(c for c in controls if c['label'] == '可使用权限')
        self.assertEqual(card['attributes'], ['AXDescription', 'AXHelp'])
        self.assertEqual(card['match'], 'exact')
        serialized = json.dumps(controls, ensure_ascii=False)
        for private in ('private bot name', 'private permission description', '授权消息'):
            self.assertNotIn(private, serialized)
        self.assertNotIn('消息', [c['label'] for c in controls])

    def test_contained_heading_is_not_reported_as_an_exact_click_target(self):
        ax = self.adapter()
        card = node('AXGroup', '可使用权限\nprivate composite description')
        labels = inspection.native_labels(ax, card)
        self.assertEqual(labels, [{'label': '可使用权限', 'match': 'contained', 'attributes': ['AXTitle']}])
        detail = inspection.native_labels(ax, node('AXImage', '机器人详情'))
        self.assertEqual([v['label'] for v in detail], ['机器人详情'])

    def test_contacts_outline_is_distinct_from_management_cards_and_omits_names(self):
        ax = self.adapter()
        def row(name, icon, y):
            return node('AXRow', frame=(20,y,200,30), children=[
                node('AXTextArea', AXValue=name), node('AXImage', AXDescription=icon)])
        outline = node('AXOutline', frame=(20,20,220,300), children=[
            row('智能机器人','avatar starred bot selected',20),
            row(self.cfg['bot_chat_name'],'icon bot',60),
            row('private other Bot','icon bot',100),
            row('private organization','avatar company',140),
            row(self.cfg['bot_chat_name'],'icon bot',180)])
        ax.window['AXChildren'].append(outline)
        result = inspection.inspect_desktop(self.cfg, ax)
        directory = result['windows'][0]['bot_directories'][0]
        self.assertEqual(directory['kind'],'contacts_bot_directory')
        self.assertEqual(directory['visible_bot_rows'],2)
        self.assertEqual(len(directory['configured_name_candidates']),1)
        self.assertFalse(directory['list_complete'])
        self.assertFalse(directory['target_identity_verified'])
        encoded=json.dumps(directory)
        self.assertNotIn('private',encoded)
        self.assertNotIn(self.cfg['bot_chat_name'],encoded)
        initial = inspection.inspect_desktop(None, ax)
        self.assertFalse(initial['target_configured'])
        listing = initial['windows'][0]['bot_directories'][0]
        self.assertEqual([b['display_name'] for b in listing['bot_candidates']],
                         [self.cfg['bot_chat_name'],'private other Bot'])
        self.assertNotIn('private organization',json.dumps(initial))
        self.assertNotIn('target_rows',initial['windows'][0]['official_permission_pages'][0])
        self.assertFalse(initial['windows'][0]['official_permission_pages'][0]['matches_configured_bot'])
        # A page can mention the same heading/name without being a directory.
        outline['AXRole']='AXTable'
        self.assertEqual(inspection.inspect_desktop(self.cfg,ax)['windows'][0]['bot_directories'],[])
        outline['AXRole']='AXOutline'
        outline['AXChildren'][0]['AXChildren'][1]['AXDescription']='unrelated icon'
        self.assertEqual(inspection.inspect_desktop(self.cfg,ax)['windows'][0]['bot_directories'],[])
