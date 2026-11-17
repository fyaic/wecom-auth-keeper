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
        # 2026-11-17：打字期下拉（实测形态 320×702，行=精确同名静态文本，
        # 界内）；选择会话不再 Return（Return 已实测改为打开全局搜索对话框）。
        self.dropdown_row = node('AXStaticText', cfg['bot_chat_name'], _frame=(249, 182, 72, 20))
        self.dropdown = node('AXWindow', _frame=(188, 136, 320, 702),
                             children=[self.dropdown_row])
        self.app['AXWindows'] = [self.window, self.dropdown]
        self.inputs = []
        self.submits = []
        self.set_values = []
        self.set_value_error = False
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

    def set_value(self, element, value):
        if self.set_value_error:
            raise RuntimeError('set_value failed')
        self.set_values.append((element, value))
        element['AXValue'] = value
        # 与真实 AXUIElementSetAttributeValue 语义一致：0=成功，失败返回
        # 非 0 错误码而不抛（门审轮2 P2-C 旋钮）
        return getattr(self, 'set_value_code', 0)

    def click(self, element, window):
        self.clicks.append(element)
        if element is self.dropdown_row:
            self.heading['AXTitle'] = self.selected_title
        elif element is self.history:
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
        # 2026-11-17：验名行点击取代 Return（绝不 submit）
        self.assertEqual(ax.submits, [])
        self.assertEqual(ax.clicks, [ax.dropdown_row, ax.history, ax.link])

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
        # 行点击后 heading 验证失败即止——history/link 绝不被点
        self.assertEqual(ax.clicks, [ax.dropdown_row])
        self.assertEqual(ax.submits, [])

    def test_same_name_wrong_bot_link_never_clicked(self):
        ax = NavigationAX(self.cfg)
        ax.link['AXURL'] = ax.page['AXURL'].replace('str_aibotid=fixture', 'str_aibotid=another')
        with self.assertRaises(KeeperError) as caught:
            self.engine(ax).open()
        self.assertEqual(caught.exception.code, 'link_not_visible')
        self.assertEqual(ax.clicks, [ax.dropdown_row, ax.history])

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
        self.assertEqual(ax.clicks, [ax.dropdown_row, ax.history])

    def test_navigation_config_requires_boolean(self):
        self.cfg['chat_history_navigation'] = 'true'
        with self.assertRaises(KeeperError):
            load_config(self.write_config())



class ChatSelectionTests(Fixture):
    """2026-11-17 修复层：验名行点击取代 Return（AZW 每小时残窗根因）。"""

    def setUp(self):
        super().setUp()
        self.cfg['chat_history_navigation'] = True

    def test_ambiguous_exact_rows_refuse_to_click(self):
        ax = NavigationAX(self.cfg)
        ax.app['AXWindows'].append(node('AXWindow', _frame=(600, 136, 320, 702), children=[
            node('AXStaticText', 'fixture', _frame=(650, 182, 72, 20))]))
        with self.assertRaises(KeeperError) as caught:
            self.engine(ax).open()
        self.assertEqual(caught.exception.code, 'navigation_target_not_found')
        self.assertEqual(ax.clicks, [])
        self.assertEqual(ax.submits, [])

    def test_out_of_bounds_rows_are_ignored(self):
        ax = NavigationAX(self.cfg)
        # 主窗 below-fold 虚拟坐标行（实测 y≈2672）：界外，绝不可点
        ax.dropdown['AXChildren'] = [node('AXStaticText', 'fixture',
                                          _frame=(249, 2672, 72, 20))]
        with self.assertRaises(KeeperError) as caught:
            self.engine(ax).open()
        self.assertEqual(caught.exception.code, 'navigation_target_not_found')
        self.assertEqual(ax.clicks, [])
        self.assertEqual(ax.submits, [])

    def test_dropdown_without_target_row_times_out_honestly(self):
        ax = NavigationAX(self.cfg)
        ax.dropdown['AXChildren'] = [node('AXStaticText', '别的会话',
                                          _frame=(249, 182, 120, 20))]
        with self.assertRaises(KeeperError) as caught:
            self.engine(ax).open()
        self.assertEqual(caught.exception.code, 'navigation_target_not_found')
        self.assertEqual(ax.clicks, [])
        self.assertEqual(ax.submits, [])


class RestoreNavigationTests(Fixture):
    """2026-11-17 清理军链：导航遗留面板的 best-effort 收场。"""

    def _engine(self, ax):
        engine = self.engine(ax)
        engine.app = ax.app  # restore_navigation 在 open 之后调用（app 已绑定）
        return engine

    def _ax_with_panel_open(self):
        ax = NavigationAX(self.cfg)
        ax.history['AXTitle'] = '关闭聊天记录'
        return ax

    def test_clears_search_and_closes_open_history_panel(self):
        from keeper_navigation import restore_navigation
        ax = self._ax_with_panel_open()
        steps = restore_navigation(self._engine(ax))
        self.assertEqual(steps, {'search_cleared': True, 'history_panel_closed': True})
        self.assertIn((ax.search, ''), ax.set_values)
        self.assertIn(ax.history, ax.clicks)

    def test_no_panel_open_clears_search_only(self):
        from keeper_navigation import restore_navigation
        ax = NavigationAX(self.cfg)
        steps = restore_navigation(self._engine(ax))
        self.assertEqual(steps, {'search_cleared': True})
        self.assertIn((ax.search, ''), ax.set_values)

    def test_step_isolation_search_failure_does_not_swallow_panel_close(self):
        from keeper_navigation import restore_navigation
        ax = self._ax_with_panel_open()
        ax.set_value_error = True
        steps = restore_navigation(self._engine(ax))
        self.assertEqual(steps, {'search_cleared': False, 'history_panel_closed': True})
        self.assertIn(ax.history, ax.clicks)

    def test_set_value_error_code_reports_false(self):
        # 门审轮2 P2-C：真实 AX 失败形态是返回非 0 不抛——不得误报成功
        from keeper_navigation import restore_navigation
        ax = NavigationAX(self.cfg)
        ax.set_value_code = -25200  # kAXErrorCannotComplete
        steps = restore_navigation(self._engine(ax))
        self.assertEqual(steps, {'search_cleared': False})

    def test_multi_window_clear_aggregates_all(self):
        # 门审轮2 P2-C/P2-5：多窗任一失败 ⇒ 聚合为 False
        from keeper_navigation import restore_navigation
        ax = NavigationAX(self.cfg)
        second = node('AXWindow', _frame=(1200, 88, 900, 800), children=[
            node('AXTextField', _frame=(1240, 103, 180, 34))])
        ax.app['AXWindows'].append(second)
        original = ax.set_value

        def coded(element, value):
            result = original(element, value)
            return -25200 if element is second['AXChildren'][0] else result
        ax.set_value = coded
        steps = restore_navigation(self._engine(ax))
        self.assertEqual(steps, {'search_cleared': False})
