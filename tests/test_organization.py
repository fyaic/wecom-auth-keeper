from unittest.mock import patch
from keeper_common import KeeperError
from keeper_organization import menu_rows, ensure_organization
from test_keeper import Fixture, node
from test_navigation import NavigationAX


def corp(name, selected=False):
    return node('AXRow', children=[node('AXStaticText', name),
        node('AXImage', AXDescription='icon corp list selected' if selected else 'icon corp list unselected'),
        node('AXImage', AXDescription='icon corp checkmark' if selected else '')])


class OrganizationTests(Fixture):
    def setUp(self):
        super().setUp()
        self.cfg.update(organization_selector_name='target', organization_navigation='sidebar-5.0.13')
        self.ax = NavigationAX(self.cfg)
        self.ax.client_version = lambda _: '5.0.13'
        self.popup = node('AXWindow', children=[corp('other', True), corp('target')], _frame=(0, 300, 240, 270))
        self.entries = 0
        self.original_click = self.ax.click
        self.ax.open_organization_menu = self.toggle
        self.ax.click = self.choose
        self.engine_instance = self.engine(self.ax)
        self.engine_instance.app = self.ax.app

    def toggle(self, *args):
        self.entries += 1
        windows = self.ax.app['AXWindows']
        if self.popup in windows: windows.remove(self.popup)
        else: windows.append(self.popup)

    def choose(self, row, window):
        self.ax.clicks.append(row)
        if row is self.ax.search and self.popup in self.ax.app['AXWindows']:
            self.ax.app['AXWindows'].remove(self.popup)
        elif window is self.popup:
            self.popup['AXChildren'] = [corp('other'), corp('target', True)]
            self.ax.app['AXWindows'].remove(self.popup)

    def test_switch_verified_selected_marker_and_menu_closed(self):
        result = ensure_organization(self.engine_instance, None)
        self.assertTrue(result['switched'])
        self.assertEqual(self.entries, 2)
        self.assertNotIn(self.popup, self.ax.app['AXWindows'])

    def test_same_org_is_verified_not_inferred_from_chat(self):
        self.popup['AXChildren'] = [corp('target', True)]
        self.assertFalse(ensure_organization(self.engine_instance, None)['switched'])

    def test_unknown_version_does_not_click(self):
        self.ax.client_version = lambda _: '5.0.14'
        with self.assertRaises(KeeperError): ensure_organization(self.engine_instance, None)
        self.assertEqual(self.entries, 0)

    def test_duplicate_name_does_not_choose(self):
        self.popup['AXChildren'].append(corp('target'))
        with self.assertRaises(KeeperError): ensure_organization(self.engine_instance, None)
        self.assertFalse(any(n.get('AXRole') == 'AXRow' for n in self.ax.clicks))
        self.assertNotIn(self.popup, self.ax.app['AXWindows'])

    def test_substring_name_does_not_choose(self):
        self.cfg['organization_selector_name'] = 'tar'
        with self.assertRaises(KeeperError): ensure_organization(self.engine_instance, None)
        self.assertFalse(any(n.get('AXRole') == 'AXRow' for n in self.ax.clicks))

    def test_names_in_chat_do_not_count_as_org(self):
        self.ax.window['AXChildren'].append(corp('target', True))
        self.assertEqual(menu_rows(self.engine_instance), [])

    def test_missing_selected_marker_stops(self):
        self.popup['AXChildren'] = [corp('target')]
        with self.assertRaises(KeeperError): ensure_organization(self.engine_instance, None)
        self.assertFalse(any(n.get('AXRole') == 'AXRow' for n in self.ax.clicks))

    def test_failed_switch_not_reported_success(self):
        self.ax.click = lambda row, window: self.ax.app['AXWindows'].remove(self.popup)
        with self.assertRaises(KeeperError) as caught: ensure_organization(self.engine_instance, None)
        self.assertEqual(caught.exception.code, 'organization_switch_timeout')
