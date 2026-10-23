"""Full native-search -> history -> bound-page fixtures; never use a real desktop."""
from keeper_common import KeeperError, load_config
from keeper_navigation import heading_matches
from test_keeper import FakeAX, Fixture, node


class NavigationAX(FakeAX):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.permission_window = self.window
        self.search = node('AXTextField', x=80, y=20, _frame=(80, 20, 180, 30))
        self.heading = node('AXStaticText', 'another chat', x=350, y=20)
        self.history = node('AXButton', '查找聊天记录', x=500, y=500)
        self.history_search = node('AXTextField', x=650, y=130)
        self.link = node('AXLink', AXURL=self.page['AXURL'], x=650, y=220)
        self.history_scroll = node('AXScrollArea', _frame=(600, 180, 290, 400))
        self.window = node('AXWindow', '企业微信', children=[
            self.search, self.heading, self.history], _frame=(0, 0, 900, 800))
        self.app['AXWindows'] = [self.window]
        self.inputs = []
        self.submits = []
        self.selected_title = cfg['bot_chat_name']
        self.focus_error = False

    def ax_perform(self, element, action):
        if self.focus_error:
            return 1
        self.app['AXFocusedWindow'] = element
        return 0

    def replace_search(self, native, app, window, element, text):
        self.inputs.append(text)
        element['AXValue'] = text
        if element is self.history_search:
            self.history_scroll['AXChildren'] = [self.link]

    def submit_search(self, native, app, window, element, expected):
        self.submits.append(expected)
        self.heading['AXTitle'] = self.selected_title

    def click(self, element, window):
        self.clicks.append(element)
        if element is self.history:
            self.history['AXTitle'] = '关闭聊天记录'
            self.window['AXChildren'].extend([self.history_search, self.history_scroll])
        elif element is self.link:
            self.app['AXWindows'].append(self.permission_window)


class NavigationTests(Fixture):
    def setUp(self):
        super().setUp()
        self.cfg['chat_history_navigation'] = True

    def test_other_chat_to_verified_page_without_messages(self):
        ax = NavigationAX(self.cfg)
        engine = self.engine(ax)
        self.assertIs(engine.open(), ax.permission_window)
        self.assertEqual(ax.inputs, ['fixture', 'authorizationList'])
        self.assertEqual(ax.submits, ['fixture'])
        self.assertEqual(ax.clicks, [ax.history, ax.link])

    def test_group_chat_editable_title_is_not_global_search(self):
        ax = NavigationAX(self.cfg)
        ax.heading['AXRole'] = 'AXTextField'
        self.assertIs(self.engine(ax).open(), ax.permission_window)

    def test_opt_in_does_not_override_existing_window_only(self):
        ax = NavigationAX(self.cfg)
        with self.assertRaises(KeeperError) as caught:
            self.engine(ax).open(existing_only=True)
        self.assertEqual(caught.exception.code, 'page_not_open')
        self.assertEqual(ax.inputs, [])

    def test_toolbar_history_name_can_be_exposed_only_as_help(self):
        ax = NavigationAX(self.cfg)
        ax.history['AXTitle'] = ''
        ax.history['AXHelp'] = '查找聊天记录'
        self.assertIs(self.engine(ax).open(), ax.permission_window)

    def test_default_does_not_search_chats(self):
        self.cfg.pop('chat_history_navigation')
        ax = NavigationAX(self.cfg)
        with self.assertRaises(KeeperError):
            self.engine(ax).open()
        self.assertEqual(ax.inputs, [])

    def test_wrong_search_result_never_queries_history_or_clicks_link(self):
        ax = NavigationAX(self.cfg)
        ax.selected_title = 'fixture extra'
        with self.assertRaises(KeeperError) as caught:
            self.engine(ax).open()
        self.assertEqual(caught.exception.code, 'navigation_target_not_found')
        self.assertEqual(ax.inputs, ['fixture'])
        self.assertEqual(ax.clicks, [])

    def test_same_name_wrong_bot_link_never_clicked(self):
        ax = NavigationAX(self.cfg)
        ax.link['AXURL'] = ax.page['AXURL'].replace('str_aibotid=fixture', 'str_aibotid=another')
        with self.assertRaises(KeeperError) as caught:
            self.engine(ax).open()
        self.assertEqual(caught.exception.code, 'link_not_visible')
        self.assertEqual(ax.clicks, [ax.history])

    def test_target_title_inside_conversation_is_not_header(self):
        ax = NavigationAX(self.cfg)
        ax.window['AXChildren'].append(node('AXScrollArea', children=[
            node('AXStaticText', 'fixture', x=350, y=20)]))
        self.assertFalse(heading_matches(self.engine(ax), ax.window, ax.search))

    def test_already_target_does_not_reselect_chat(self):
        ax = NavigationAX(self.cfg)
        ax.heading['AXTitle'] = 'fixture'
        self.assertIs(self.engine(ax).open(), ax.permission_window)
        self.assertEqual(ax.inputs, ['authorizationList'])
        self.assertEqual(ax.submits, [])

    def test_duplicate_main_windows_fail_without_input(self):
        ax = NavigationAX(self.cfg)
        ax.app['AXWindows'].append(ax.window)
        with self.assertRaises(KeeperError) as caught:
            self.engine(ax).open()
        self.assertEqual(caught.exception.code, 'navigation_unavailable')
        self.assertEqual(ax.inputs, [])

    def test_raise_failure_prevents_keyboard_input(self):
        ax = NavigationAX(self.cfg)
        ax.focus_error = True
        with self.assertRaises(KeeperError):
            self.engine(ax).open()
        self.assertEqual(ax.inputs, [])

    def test_chat_switch_during_history_search_stops_before_link(self):
        ax = NavigationAX(self.cfg)
        replace = ax.replace_search
        def changed(native, app, window, element, text):
            replace(native, app, window, element, text)
            if element is ax.history_search:
                ax.heading['AXTitle'] = 'another'
        ax.replace_search = changed
        with self.assertRaises(KeeperError) as caught:
            self.engine(ax).open()
        self.assertEqual(caught.exception.code, 'navigation_target_changed')
        self.assertEqual(ax.clicks, [ax.history])

    def test_navigation_config_requires_boolean(self):
        self.cfg['chat_history_navigation'] = 'true'
        with self.assertRaises(KeeperError):
            load_config(self.write_config())
