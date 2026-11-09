import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from keeper_bootstrap import authorization_identity
from test_delivery import module

entry = module('existing_entry')
URL = 'https://work.weixin.qq.com/ai/aiHelper/authorizationList?from=chat&forceInnerBrowser=1&aibotid=123&str_aibotid=fixture&type=6&pc_bar_bg=%23FFFFFF&for_native=1'


class ExistingEntryTests(unittest.TestCase):
    def test_reuses_explicit_profile_without_rebinding_or_printing_identity(self):
        calls=[]
        def run(args, **kwargs):
            calls.append((args[1:],kwargs['env']))
            out={('--version',):'wecom-cli 1.3.0', ('auth','show','--status'):'authorized',
                 ('auth','show'):'Bot ID: fixture\n', ('identity','whoami'):json.dumps({'context':'Business Bot'}),
                 ('message','aibot','sessions','list'):json.dumps({'errcode':850003,'help_message':'[续期]('+URL+')'})}[tuple(args[1:])]
            return subprocess.CompletedProcess(args,1 if args[1]=='message' else 0,out,'')
        with tempfile.TemporaryDirectory() as d, patch.object(entry,'executable',return_value='/cli'):
            output=Path(d)/'evidence.json'
            result=entry.inspect_existing({'wecom_cli':'/cli','cli_config_dir':'/selected'},output,run=run)
            report=json.loads(output.read_text())
            self.assertEqual(report['authorization_url'],URL)
            self.assertEqual(report['cli_bot_id'],'fixture')
            self.assertFalse(report['organization_verified'])
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
            self.assertNotIn('fixture',json.dumps(result))
            self.assertTrue(all(env['WECOM_CLI_CONFIG_DIR']=='/selected' for _,env in calls))
            self.assertFalse(any('init' in args or 'send' in args for args,_ in calls))
            with self.assertRaises(FileExistsError):entry.inspect_existing({},output,run=run)

    def test_wrong_or_ambiguous_official_link_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'cli_bot_identity_mismatch'):
            entry.official_url({'help_message':URL},'different')
        for message in ('no link',URL+' '+URL+'&ww_vw=100', URL.replace('work.weixin.qq.com','evil.example')):
            with self.assertRaisesRegex(ValueError,'official_authorization_url_unavailable'):
                entry.official_url({'help_message':message},'fixture')

    def test_url_rejects_blank_duplicate_identity_and_unsafe_components(self):
        for url in (URL+'&aibotid=', URL+'&str_aibotid=',URL.replace('fixture','%0Afixture'),
                    URL+'#fragment',URL.replace('https:','http:'),URL.replace('.com/','.com:bad/'),
                    URL.replace('work.weixin.qq.com','evil@work.weixin.qq.com')):
            with self.assertRaisesRegex(ValueError,'invalid_authorization_url'):authorization_identity(url)

    def test_unauthorized_profile_does_not_start_a_qr_flow(self):
        calls=[]
        def run(args, **kwargs):
            calls.append(args[1:])
            return subprocess.CompletedProcess(args,0,'wecom-cli 1.3.0' if args[1]=='--version' else 'unauthorized','')
        with tempfile.TemporaryDirectory() as d, patch.object(entry,'executable',return_value='/cli'):
            with self.assertRaisesRegex(ValueError,'existing_profile_not_authorized'):
                entry.inspect_existing({},Path(d)/'private.json',run=run)
        self.assertEqual(calls,[['--version'],['auth','show','--status']])

    def test_profile_changed_during_query_cannot_produce_a_valid_entry(self):
        count=0
        def run(args, **kwargs):
            nonlocal count
            if args[1:]==['auth','show']:
                count+=1
                out='Bot ID: '+('fixture' if count==1 else 'changed')+'\n'
            else:
                out={('--version',):'wecom-cli 1.3.0', ('auth','show','--status'):'authorized',
                     ('identity','whoami'):'{}',('message','aibot','sessions','list'):json.dumps({'errcode':850003,'help_message':URL})}[tuple(args[1:])]
            return subprocess.CompletedProcess(args,0,out,'')
        with tempfile.TemporaryDirectory() as d, patch.object(entry,'executable',return_value='/cli'):
            with self.assertRaisesRegex(ValueError,'cli_profile_changed'):
                entry.inspect_existing({},Path(d)/'private.json',run=run)
