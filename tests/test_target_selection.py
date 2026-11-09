import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from test_delivery import module, selection_for
from test_existing_entry import URL
from keeper_bootstrap import validate_target_selection

selector = module('select_target')
onboard = module('onboard')
profiles = module('profiles')
entry = module('existing_entry')


class TargetSelectionTests(unittest.TestCase):
    def target(self):
        return {'selection_source':'user_request', 'identity_source':'native_selected_bot_permission_page',
                'bot_chat_name':'Test Bot', 'organization_selector_name':'Test Org', 'authorization_url':URL}

    def inventory(self, ids):
        return {'schema_version':2,'profiles':[{'status':'authorized','cli_config_dir':path,'cli_bot_id':bot}
                                               for path,bot in ids]}

    def test_authorized_default_cannot_replace_requested_bot(self):
        result=selector.select(self.target(),self.inventory([(None,'business-bot'),('/kaopu','second-business-bot')]))
        self.assertFalse(result['ok']);self.assertEqual(result['status'],'target_profile_not_found')
        self.assertEqual(result['bot_chat_name'],'Test Bot')
        self.assertFalse(result['requested_target_changed']);self.assertNotIn('cli_config_dir',result)
        self.assertEqual(result['inventory_scope'],'explicit_profiles_only')

    def test_matching_nondefault_wins_by_id_not_display_name_or_order(self):
        result=selector.select(self.target(),self.inventory([(None,'wrong'),('/test','fixture')]))
        self.assertTrue(result['ok']);self.assertEqual(result['cli_config_dir'],'/test')
        self.assertFalse(result['desktop_creator_verified'])

    def test_multiple_matching_profiles_require_explicit_resolution(self):
        result=selector.select(self.target(),self.inventory([(None,'fixture'),('/test','fixture')]))
        self.assertFalse(result['ok']);self.assertEqual(result['status'],'target_profile_ambiguous')
        self.assertNotIn('cli_config_dir',result)

    def test_incomplete_or_forged_success_record_cannot_select_a_profile(self):
        selection=selector.select(self.target(),self.inventory([(None,'fixture')]))
        for key in ('cli_config_dir', 'authorization_url', 'matching_profile_count', 'requested_target_changed'):
            incomplete=dict(selection);del incomplete[key]
            with self.assertRaisesRegex(ValueError,'target_selection_required'):
                validate_target_selection(incomplete)
        for change in ({'cli_bot_id':'wrong'}, {'matching_profile_count':2}, {'cli_config_dir':'relative/path'}):
            with self.assertRaisesRegex(ValueError,'target_selection_required'):
                validate_target_selection({**selection,**change})

    def test_name_only_or_unstable_profile_is_not_identity(self):
        inv=self.inventory([(None,'fixture')]);inv['profiles'][0]['status']='identity_unstable'
        self.assertFalse(selector.select(self.target(),inv)['ok'])
        inv['profiles'][0]={'cli_config_dir':None,'status':'authorized','identity':{'name':'Test Bot'}}
        self.assertFalse(selector.select(self.target(),inv)['ok'])
        with self.assertRaisesRegex(ValueError,'profile_inventory_requires_refresh'):
            selector.select(self.target(),{'schema_version':1,'profiles':[]})

    def test_onboarding_requires_selection_and_rejects_target_or_profile_drift(self):
        value={k:v for k,v in self.target().items() if k not in ('selection_source','identity_source')}
        value.update(cli_bot_id='fixture',organization_name='Test Org',target_rows=['发送消息'])
        selection=selection_for(value)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.json'
            with self.assertRaisesRegex(ValueError,'target_selection_required'):onboard.configure(value,p,'Darwin')
            for change in ({'bot_chat_name':'Default business Bot'}, {'cli_config_dir':'/business'},
                           {'organization_selector_name':'Other Org'}):
                with self.assertRaisesRegex(ValueError,'requested_target_mismatch'):
                    onboard.configure({**value,**change},p,'Darwin',selection=selection)
                self.assertFalse(p.exists())

    def test_existing_entry_stops_wrong_profile_before_business_query(self):
        calls=[]
        def run(args, **kwargs):
            calls.append(args[1:])
            value={('--version',):'wecom-cli 1.3.0',('auth','show','--status'):'authorized',
                   ('auth','show'):'Bot ID: wrong-default\n'}[tuple(args[1:])]
            return subprocess.CompletedProcess(args,0,value,'')
        with tempfile.TemporaryDirectory() as d,patch.object(entry,'executable',return_value='/cli'):
            with self.assertRaisesRegex(ValueError,'requested_target_mismatch'):
                entry.inspect_existing({'expected_bot_id':'fixture'},Path(d)/'out.json',run=run)
        self.assertEqual(calls,[['--version'],['auth','show','--status'],['auth','show']])

    def test_inventory_records_official_id_only_when_stable(self):
        calls=[];counts={}
        def run(args, **kwargs):
            env=kwargs['env'];profile=env.get('WECOM_CLI_CONFIG_DIR');calls.append(args[1:])
            if args[1:]==['auth','show']:
                counts[profile]=counts.get(profile,0)+1
                bot='changed' if profile=='/unstable' and counts[profile]>1 else 'fixture'
                out='Bot ID: '+bot+'\n'
            else:
                out={('--version',):'wecom-cli 1.3.0',('auth','show','--status'):'authorized',
                     ('identity','whoami'):'{}'}[tuple(args[1:])]
            return subprocess.CompletedProcess(args,0,out,'')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'profiles.json'
            result=profiles.inspect_profiles('/cli',['/unstable'],p,run=run)
            report=json.loads(p.read_text())
        self.assertFalse(result['ok'])
        self.assertEqual(report['profiles'][0]['cli_bot_id'],'fixture')
        self.assertEqual(report['profiles'][1]['status'],'identity_unstable')
        self.assertNotIn('cli_bot_id',report['profiles'][1])
        self.assertFalse(any('init' in c or 'send' in c for c in calls))
