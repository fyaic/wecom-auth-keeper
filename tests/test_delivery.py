import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from keeper_common import KeeperError

ROOT = Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'delivery'/f'{name}.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
onboard = module('onboard')
verify = module('verify_bundle')
builder = module('build_bundle')
gui = module('gui')
discovery = module('discover')

class DeliveryTests(unittest.TestCase):
    def data(self):
        return {'bot_chat_name':'fixture','organization_name':'fixture org', 'cli_bot_id':'fixture',
                'authorization_url':'https://work.weixin.qq.com/ai/aiHelper/authorizationList?aibotid=123&str_aibotid=fixture',
                'target_rows':['发送消息','搜索与获取文档内容']}

    def test_windows_stops_before_native_import_or_config(self):
        self.assertEqual(onboard.detect('Windows')['status'],'unsupported_automation_backend')
        with self.assertRaisesRegex(ValueError,'unsupported_automation_backend'):
            onboard.configure({},'/unused','Windows')

    def test_private_config_defaults_do_not_enable_heuristic_org_switch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'private.json'
            self.assertTrue(onboard.configure(self.data(),p,'Darwin')['ok'])
            cfg=json.loads(p.read_text())
            self.assertEqual(cfg['maintenance']['within_hours'],24)
            self.assertEqual(len(cfg['target_rows']),2)
            self.assertNotIn('organization_name',cfg)
            self.assertEqual(p.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError): onboard.configure(self.data(),p,'Darwin')

    def test_wrong_bot_url_or_scope_never_writes(self):
        variants=[{'cli_bot_id':'another'}, {'target_rows':['未知权限']}, {'target_rows':['发送消息','发送消息']},
                  {'authorization_url':self.data()['authorization_url'].replace('https:','http:')},
                  {'authorization_url':self.data()['authorization_url']+'&aibotid=456'},
                  {'authorization_url':self.data()['authorization_url'].replace('work.weixin.qq.com','evil.example')},
                  {'bot_chat_name':'<placeholder>'}]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'private.json'
            for change in variants:
                with self.assertRaises(ValueError): onboard.configure({**self.data(),**change},p,'Darwin')
                self.assertFalse(p.exists())

    def test_package_disallows_sensitive_source_paths(self):
        self.assertNotIn('config.didadi.example.json',builder.FILES)
        self.assertNotIn('scripts/inspect_compat.py',builder.FILES)
        self.assertTrue(all(not n.endswith(('.log','.env')) for n in builder.FILES))
        with self.assertRaises(ValueError): onboard.configure(self.data(),ROOT/'private.json','Darwin')

    def test_integrity_rejects_tampering_and_traversal(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'a').write_text('test')
            manifest=p/'MANIFEST.json';manifest.write_text(json.dumps({'files':{'a':hashlib.sha256(b'test').hexdigest()}}))
            self.assertTrue(verify.verify(p))
            (p/'a').write_text('changed'); self.assertFalse(verify.verify(p))
            manifest.write_text(json.dumps({'files':{'../outside':'bad'}}));self.assertFalse(verify.verify(p))

    def test_gui_actions_use_public_bounded_maintenance_and_never_shell(self):
        args = gui.command('maintain', '/path with space/python', '/private/config.json')
        self.assertNotIn('--worker', args)
        self.assertEqual(args[0], '/path with space/python')
        self.assertEqual(Path(args[1]).name, 'maintain.py')
        read_args = gui.command('check-existing', '/python', '/private/config.json')
        self.assertEqual(Path(read_args[1]).name, 'renew.py')
        self.assertEqual(read_args[-2:], ['--check', '--existing-window'])
        with patch.object(gui.sys, 'platform', 'win32'):
            with self.assertRaisesRegex(ValueError, 'unsupported_automation_backend'):
                gui.run_once('check', '/does/not/exist', '/unused')

    def test_discovery_distinguishes_name_from_id_and_restores_original(self):
        engine = Mock(); engine.cfg = {}; engine.visible_links.return_value = []
        ax = Mock(); ax.application.return_value = (None, None)
        selected = []
        def select(e, _): selected.append(e.cfg['organization_selector_name'])
        with patch.object(discovery, 'Renewal', return_value=engine), \
             patch.object(discovery, 'list_organizations', return_value=[{'name':'A','selected':True},{'name':'B','selected':False}]), \
             patch.object(discovery, 'ensure_organization', side_effect=select), \
             patch.object(discovery, 'open_chat', return_value=(None,None)), \
             patch.object(discovery, 'open_chat_history', side_effect=KeeperError('link_not_visible','missing')):
            result = discovery.discover({},ax)
        self.assertEqual(result['verified_organizations'], [])
        self.assertEqual(result['status'], 'identity_review_required')
        self.assertTrue(all(r['chat_name_matched'] for r in result['organizations']))
        self.assertEqual(selected, ['A','B','A'])

    def test_discovery_stops_on_focus_loss_and_restores_original(self):
        engine = Mock(); engine.cfg = {}
        ax = Mock(); ax.application.return_value = (None,None)
        with patch.object(discovery,'Renewal',return_value=engine), \
             patch.object(discovery,'list_organizations',return_value=[{'name':'A','selected':True}]), \
             patch.object(discovery,'ensure_organization') as select, \
             patch.object(discovery,'open_chat',side_effect=KeeperError('navigation_focus_lost','lost')):
            with self.assertRaises(KeeperError): discovery.discover({},ax)
        self.assertEqual(select.call_count,2)

    def test_discovery_preserves_primary_failure_when_restore_also_fails(self):
        engine = Mock(); engine.cfg = {}
        ax = Mock(); ax.application.return_value = (None,None)
        with patch.object(discovery,'Renewal',return_value=engine), \
             patch.object(discovery,'list_organizations',return_value=[{'name':'A','selected':True}]), \
             patch.object(discovery,'ensure_organization',side_effect=[None,KeeperError('org_switcher_not_found','restore')]), \
             patch.object(discovery,'open_chat',side_effect=KeeperError('navigation_focus_lost','lost')):
            with self.assertRaises(KeeperError) as caught:
                discovery.discover({},ax)
        self.assertEqual(caught.exception.code,'navigation_focus_lost')
        evidence = caught.exception.discovery
        self.assertFalse(evidence['ok'])
        self.assertEqual(evidence['stage'],'finding_chat_entry')
        self.assertEqual(evidence['enumerated_organizations'],['A'])
        self.assertEqual(evidence['cleanup']['error'],'org_switcher_not_found')

    def test_discovery_keeps_partial_coverage_on_later_org_failure(self):
        engine = Mock(); engine.cfg = {}; engine.visible_links.return_value=[]
        ax = Mock(); ax.application.return_value = (None,None)
        with patch.object(discovery,'Renewal',return_value=engine), \
             patch.object(discovery,'list_organizations',return_value=[{'name':'A','selected':True},{'name':'B','selected':False}]), \
             patch.object(discovery,'ensure_organization',side_effect=[None,KeeperError('org_switcher_not_found','target'),None]), \
             patch.object(discovery,'open_chat',side_effect=KeeperError('navigation_target_not_found','none')):
            with self.assertRaises(KeeperError) as caught:
                discovery.discover({},ax)
        evidence=caught.exception.discovery
        self.assertEqual(evidence['stage'],'selecting_organization')
        self.assertEqual(evidence['current_candidate'],'B')
        self.assertEqual(evidence['organizations'][0]['error'],'navigation_target_not_found')
        self.assertEqual(len(evidence['organizations']),2)
        self.assertTrue(evidence['cleanup']['ok'])
