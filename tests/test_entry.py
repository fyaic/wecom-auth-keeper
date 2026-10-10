"""Verified-link entry fixtures; never read or operate a real desktop."""
from keeper_common import KeeperError
from test_keeper import FakeAX, Fixture, node


class EntryAX(FakeAX):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.permission_window = self.window
        self.link = node('AXLink', AXURL=self.page['AXURL'])
        self.scroll = node('AXScrollArea', children=[self.link], _frame=(0, 0, 800, 500))
        self.window = node('AXWindow', '企业微信', children=[self.scroll], _frame=(0, 0, 900, 800))
        self.app['AXWindows'] = [self.window]
        self.raise_error = 0
        self.actions = []

    def ax_perform(self, element, action):
        self.actions.append(action)
        if not self.raise_error:
            self.app['AXFocusedWindow'] = element
        return self.raise_error

    def click(self, element, window):
        self.clicks.append(element)
        if element is self.link:
            self.app['AXWindows'].append(self.permission_window)


class EntryTests(Fixture):
    def test_existing_link_window_is_raised_above_auxiliary_window(self):
        ax = EntryAX(self.cfg)
        auxiliary = node('AXWindow', 'Other window')
        ax.app['AXWindows'].append(auxiliary)
        ax.app['AXFocusedWindow'] = auxiliary
        self.assertIs(self.engine(ax).open(), ax.permission_window)
        self.assertEqual(ax.actions, ['AXRaise'])
        self.assertEqual(ax.clicks, [ax.link])
        self.assertIs(ax.app['AXFocusedWindow'], ax.window)

    def test_existing_link_not_clicked_when_raise_fails(self):
        ax = EntryAX(self.cfg)
        ax.raise_error = 1
        with self.assertRaises(KeeperError):
            self.engine(ax).open()
        self.assertEqual(ax.clicks, [])

    def test_link_disappearing_during_raise_is_not_clicked(self):
        ax = EntryAX(self.cfg)
        raise_window = ax.ax_perform
        def changed(element, action):
            ax.scroll['AXChildren'].remove(ax.link)
            return raise_window(element, action)
        ax.ax_perform = changed
        with self.assertRaises(KeeperError):
            self.engine(ax).open()
        self.assertEqual(ax.clicks, [])

    def test_link_outside_scroll_viewport_is_not_clicked(self):
        ax = EntryAX(self.cfg)
        ax.link['_frame'] = (100, 700, 120, 20)
        with self.assertRaises(KeeperError):
            self.engine(ax).open()
        self.assertEqual(ax.clicks, [])

    def test_recent_name_and_prefix_collision_never_cause_a_chat_click(self):
        for text in ['fixture preview', 'fixture other-bot preview']:
            with self.subTest(text=text):
                ax = EntryAX(self.cfg)
                row = node('AXRow', children=[node('AXCell', children=[
                    node('AXStaticText', text), node('AXTextArea', AXValue='BOT\u200b')])])
                ax.scroll['AXChildren'] = [node('AXTable', children=[row])]
                with self.assertRaises(KeeperError) as error:
                    self.engine(ax).open()
                self.assertEqual(error.exception.code, 'link_not_visible')
                self.assertEqual(ax.clicks, [])
                self.assertEqual(ax.actions, [])

    def test_wrong_bot_link_never_clicked(self):
        ax = EntryAX(self.cfg)
        ax.link['AXURL'] = ax.page['AXURL'].replace('fixture', 'other-bot')
        with self.assertRaises(KeeperError):
            self.engine(ax).open()
        self.assertEqual(ax.clicks, [])

    def test_focus_must_be_verified_after_successful_raise(self):
        ax = EntryAX(self.cfg)
        ax.ax_perform = lambda element, action: 0
        with self.assertRaises(KeeperError):
            self.engine(ax).open()
        self.assertEqual(ax.clicks, [])
