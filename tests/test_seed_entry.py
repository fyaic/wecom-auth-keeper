from pathlib import Path
import json
from unittest.mock import patch
from keeper_bootstrap import entry_message
from keeper_common import KeeperError
from keeper_navigation import chat_header, chat_composer
from test_delivery import module
from test_navigation import NavigationAX
from test_keeper import Fixture, node

seed = module('seed_entry')

class SeedAX(NavigationAX):
    def __init__(self, cfg):
        super().__init__(cfg)
        self.heading['AXTitle'] = cfg['bot_chat_name']
        self.composer = node('AXTextArea', AXValue='', _frame=(350, 550, 500, 200))
        self.window['AXChildren'].append(self.composer)
        self.sent = []
        self.pasted = []
        self.after_paste = lambda: None
        self.deliver = True

    def ax_settable(self, node, attr):
        return node is self.composer and attr == 'AXValue'

    def click(self, node, window):
        self.clicks.append(node)
        self.app['AXFocusedUIElement'] = node

    def paste_composer(self, native, app, window, element, text):
        self.pasted.append(text)
        element['AXValue'] = text
        self.after_paste()

    def submit_composer(self, native, app, window, element, expected):
        self.sent.append(expected)
        element['AXValue'] = ''
        if self.deliver:
            self.link['_frame'] = (650, 220, 100, 30)
            self.window['AXChildren'].append(self.link)

class SeedTests(Fixture):
    def setUp(self):
        super().setUp()
        self.cfg['organization_selector_name'] = 'fixture org'

    def run_seed(self, ax):
        return seed.seed_current_chat(self.cfg, ax, engine=self.engine(ax))

    def test_actual_header_preserves_spaces_and_never_uses_contact_row(self):
        ax = SeedAX(self.cfg); e = self.engine(ax)
        ax.heading['AXTitle'] = 'fixture bot'
        self.assertEqual(chat_header(e, ax.window), 'fixture bot')
        ax.heading['AXTitle'] = 'fixturebot'
        self.assertEqual(chat_header(e, ax.window), 'fixturebot')
        ax.window['AXChildren'].remove(ax.heading)
        ax.window['AXChildren'].append(node('AXOutline', children=[node('AXStaticText','fixture',x=350,y=20)]))
        # AXOutline is a contacts directory, not native message chrome.
        self.assertIsNone(chat_header(e, ax.window))

    def test_contact_profile_with_editable_area_is_not_message_view(self):
        ax = SeedAX(self.cfg)
        ax.window['AXChildren'].remove(ax.history)
        ax.window['AXChildren'].extend([node('AXButton','发消息'),node('AXButton','添加到群聊')])
        self.assertIsNone(chat_composer(self.engine(ax), ax.window))
        with self.assertRaises(KeeperError): self.run_seed(ax)
        self.assertEqual(ax.sent, [])
        self.assertEqual(ax.pasted, [])

    def test_message_history_textareas_cannot_be_composer(self):
        ax=SeedAX(self.cfg)
        ax.window['AXChildren'].remove(ax.composer)
        ax.window['AXChildren'].append(node('AXScrollArea',children=[node('AXTextArea','old message',_frame=(350,550,500,200))]))
        self.assertIsNone(chat_composer(self.engine(ax),ax.window))

    def test_sends_once_then_reuses_verified_link(self):
        ax=SeedAX(self.cfg)
        self.assertEqual(self.run_seed(ax)['messages_sent'],1)
        self.assertEqual(self.run_seed(ax)['messages_sent'],0)
        self.assertEqual(ax.sent,[entry_message(self.cfg)])
        self.assertEqual(json.loads(Path(self.cfg['state_file']+'.entry-send.json').read_text())['status'],'visible_entry_verified')

    def test_existing_draft_and_wrong_header_never_receive_input(self):
        ax=SeedAX(self.cfg);ax.composer['AXValue']='user draft'
        with self.assertRaises(KeeperError): self.run_seed(ax)
        self.assertEqual(ax.pasted,[])
        self.assertEqual(ax.composer['AXValue'],'user draft')
        ax.composer['AXValue']='';ax.heading['AXTitle']='wrong'
        with self.assertRaises(KeeperError): self.run_seed(ax)
        self.assertEqual(ax.pasted,[])

    def test_conversation_changed_after_paste_never_sends(self):
        ax=SeedAX(self.cfg)
        ax.after_paste=lambda: ax.heading.update(AXTitle='other chat')
        with self.assertRaises(KeeperError): self.run_seed(ax)
        self.assertEqual(ax.sent,[])

    def test_unknown_send_outcome_never_resends(self):
        ax=SeedAX(self.cfg);ax.deliver=False
        with self.assertRaises(KeeperError): self.run_seed(ax)
        self.assertEqual(len(ax.sent),1)
        with self.assertRaises(KeeperError) as caught: self.run_seed(ax)
        self.assertEqual(caught.exception.code,'entry_send_already_attempted')
        self.assertEqual(len(ax.sent),1)
