import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'delivery'/f'{name}.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
onboard = module('onboard')
verify = module('verify_bundle')
builder = module('build_bundle')

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
