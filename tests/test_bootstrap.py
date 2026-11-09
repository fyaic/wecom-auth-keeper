from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock, patch

import maintain
from keeper_bootstrap import device_binding, entry_message, entry_status, require_entry, target_binding
from keeper_common import KeeperError, atomic_json
from test_delivery import module
from test_keeper import Fixture

entry = module('verify_entry')
prepare = module('prepare_entry')
onboard = module('onboard')


class BootstrapTests(Fixture):
    def draft(self):
        self.cfg.update(entry_receipt=str(self.root/'entry.json'), organization_selector_name='Enterprise B',
                        organization_navigation='sidebar-5.0.13', venv_python=sys.executable)
        return self.cfg

    def receipt(self):
        return dict(schema_version=1, ok=True, binding=target_binding(self.cfg), device=device_binding(),
                    cli_identity_verified=True, organization_verified=True, conversation_header_verified=True,
                    link_identity_verified=True, page_identity_verified=True, cold_start_verified=True,
                    cleanup_verified=True, entry_location='configured_bot_conversation')

    def test_no_entry_blocks_schedule_and_worker_before_any_ui(self):
        self.draft()
        with patch('maintain.process_lock') as lock, patch('maintain.supervised_worker') as worker:
            with self.assertRaises(KeeperError) as error:
                maintain.supervise(self.cfg)
            self.assertEqual(error.exception.code, 'bootstrap_incomplete')
            lock.assert_not_called(); worker.assert_not_called()
        output = self.root/'service.plist'
        with self.assertRaises(KeeperError):
            maintain.write_launchagent(self.cfg, output)
        self.assertFalse(output.exists())

    def test_receipt_cannot_follow_changed_bot_profile_org_scope_or_device(self):
        self.draft()
        atomic_json(self.cfg['entry_receipt'], self.receipt())
        self.assertEqual(entry_status(self.cfg)['status'], 'entry_navigation_verified')
        for field, value in [('aibotid', '456'), ('cli_config_dir', '/another/profile'),
                             ('organization_selector_name', 'Enterprise C'), ('target_rows', ['发送消息']),
                             ('venv_python', '/another/python'), ('bot_chat_name', 'renamed')]:
            self.assertFalse(entry_status({**self.cfg, field:value})['ok'])
        with patch('keeper_bootstrap.device_binding', return_value='other-device'):
            self.assertFalse(entry_status(self.cfg)['ok'])
        for field in ('cleanup_verified', 'cold_start_verified', 'cli_identity_verified'):
            atomic_json(self.cfg['entry_receipt'], {**self.receipt(), field:False})
            self.assertFalse(entry_status(self.cfg)['ok'])

    def test_legacy_configuration_is_not_silently_migrated(self):
        require_entry(self.cfg)
        self.assertEqual(entry_status(self.cfg)['status'], 'legacy_config_without_entry_gate')

    def test_prepare_writes_once_to_private_file_without_sending_or_printing_url(self):
        self.draft()
        p = self.root/'entry.txt'
        result = prepare.prepare(self.cfg, p)
        self.assertFalse(result['sent'])
        self.assertNotIn('authorizationList', json.dumps(result))
        self.assertIn('【自动续期入口】', p.read_text())
        self.assertIn('aibotid=123&str_aibotid=fixture', p.read_text())
        self.assertEqual(p.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError): prepare.prepare(self.cfg, p)
        with self.assertRaises(ValueError): entry_message({**self.cfg, 'organization_selector_name':''})

    def test_cli_checks_the_selected_profile_and_rejects_wrong_bot(self):
        self.draft();self.cfg['cli_config_dir']='/private/selected'
        calls=[]
        def run(args, **kwargs):
            calls.append((args[1:], kwargs['env']))
            output={('--version',):'wecom-cli 1.3.0', ('auth','show','--status'):'authorized',
                    ('auth','show'):'Status: authorized\nBot ID: other-bot\n'}[tuple(args[1:])]
            return subprocess.CompletedProcess(args,0,output,'')
        with patch.object(entry, 'executable', return_value='/wecom'):
            with self.assertRaises(KeeperError) as error:entry.verify_cli(self.cfg,run=run)
        self.assertEqual(error.exception.code, 'bootstrap_cli_identity_mismatch')
        self.assertTrue(all(env['WECOM_CLI_CONFIG_DIR']=='/private/selected' for _,env in calls))
        self.assertFalse(any('init' in args for args,_ in calls))

    def flow(self, *, same_chat=False, links=True, final_org='Enterprise B'):
        self.draft()
        engine, ax = Mock(), Mock()
        window, page, search = object(), object(), object()
        ax.application.return_value = (object(), object())
        ax.ax_get.return_value = [window]
        engine.select_window.side_effect = [None, page]
        engine.visible_links.return_value = [(0,object(),window)] if links else []
        engine.wait.side_effect = lambda read, accept, error: read()
        engine.read_rows.return_value = {n: {'status':'expired','expiry':None} for n in self.cfg['target_rows']}
        engine.close_window.return_value = ({'ok':True,'closed':True},0)
        menu = [[{'name':'Enterprise B','selected':True}], [{'name':final_org,'selected':True}]]
        patches = [patch.object(entry,'global_search',return_value=search),
                   patch.object(entry,'heading_matches',side_effect=[same_chat,True,True]),
                   patch.object(entry,'list_organizations',side_effect=menu),
                   patch.object(entry,'ensure_organization'),patch.object(entry,'open_chat_history')]
        return engine, ax, patches

    def test_prepared_entry_requires_cold_start_and_final_org_recheck(self):
        from contextlib import ExitStack
        engine,ax,patches=self.flow()
        with ExitStack() as stack:
            for p in patches:stack.enter_context(p)
            result=entry.verify_navigation(self.cfg,ax,engine=engine)
        self.assertTrue(result['ok']);self.assertFalse(result['renewal_verified'])
        self.assertFalse(result['messages_sent']);self.assertFalse(result['authorization_changed'])
        self.assertNotIn('private_chat_verified',result)
        self.assertEqual(result['private_chat_type'],'must_be_confirmed_by_installer_from_bot_details')
        engine.close_window.assert_called_once()
        for same_chat,links,org,expected in [(True,True,'Enterprise B','bootstrap_cold_start_required'),
                                            (False,False,'Enterprise B','bootstrap_entry_missing'),
                                            (False,True,'Enterprise C','bootstrap_organization_changed')]:
            engine,ax,patches=self.flow(same_chat=same_chat,links=links,final_org=org)
            with ExitStack() as stack:
                for p in patches:stack.enter_context(p)
                with self.assertRaises(KeeperError) as error:entry.verify_navigation(self.cfg,ax,engine=engine)
            self.assertEqual(error.exception.code,expected)
            if same_chat or not links:engine.open.assert_not_called()

    def test_open_timeout_still_closes_bound_page_and_preserves_primary_error(self):
        from contextlib import ExitStack
        engine,ax,patches=self.flow()
        engine.select_window.side_effect=[None, KeeperError('page_not_open','test')]
        engine.close_window.side_effect=KeeperError('window_close_failed','test')
        with ExitStack() as stack:
            for p in patches:stack.enter_context(p)
            with self.assertRaises(KeeperError) as error:entry.verify_navigation(self.cfg,ax,engine=engine)
        self.assertEqual(error.exception.code,'page_not_open')
        self.assertFalse(error.exception.entry_verification['cleanup_verified'])
        engine.close_window.assert_called_once()

    def test_failed_revalidation_invalidates_old_receipt_without_changing_config(self):
        self.draft();path=self.write_config();before=path.read_bytes()
        atomic_json(self.cfg['entry_receipt'],self.receipt())
        with patch.object(entry,'verify_cli',side_effect=KeeperError('bootstrap_cli_identity_mismatch','test')):
            with self.assertRaises(KeeperError):entry.verify_and_save(self.cfg,Mock())
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse(entry_status(self.cfg)['ok'])

    def test_success_activates_verified_adapter_and_writes_bound_receipt(self):
        self.draft();self.cfg.pop('organization_navigation')
        path=self.write_config()
        result=self.receipt()
        with patch.object(entry,'verify_cli'), patch.object(entry,'verify_navigation',return_value=result), \
             patch.object(entry,'process_lock'):
            entry.verify_and_save(self.cfg,Mock())
        active=json.loads(path.read_text())
        self.assertEqual(active['organization_navigation'],'sidebar-5.0.13')
        self.assertTrue(entry_status(active)['ok'])
        self.assertNotIn('_config_path',active)

    def test_onboarding_preserves_cli_path_for_launchd_without_terminal_path(self):
        value={'bot_chat_name':'fixture','organization_name':'Business B','organization_selector_name':'Enterprise B',
               'cli_bot_id':'fixture','authorization_url':'https://work.weixin.qq.com/ai/aiHelper/authorizationList?aibotid=123&str_aibotid=fixture',
               'target_rows':['发送消息']}
        path=self.root/'new.json'
        with patch.object(onboard.shutil,'which',return_value='/opt/homebrew/bin/wecom-cli'):
            result=onboard.configure(value,path,'Darwin')
        self.assertEqual(result['status'],'entry_preparation_required')
        cfg=json.loads(path.read_text())
        self.assertEqual(cfg['wecom_cli'],'/opt/homebrew/bin/wecom-cli')
        self.assertNotIn('organization_navigation',cfg)
        self.assertFalse(entry_status(cfg)['ok'])
