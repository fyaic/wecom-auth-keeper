import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from keeper_common import KeeperError, cli_environment, process_lock
from renew import monitor_guard
from test_delivery import module

profiles = module('profiles')
onboard = module('onboard')


class CoordinationTests(unittest.TestCase):
    def test_bridge_contract_requires_same_inode_and_never_changes_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'desktop.lock'
            with process_lock(path, 0.1):
                info = path.stat()
                response = {'protocol':'wecom-desktop-flock-v1','scope':'bridge-ui','handoff_refresh':True,
                            'lock_path':str(path),'device':info.st_dev,'inode':info.st_ino,'uid':os.getuid()}
                cfg = {'bridge_monitor':True,'bridge_coordination':'shared-lock-v1'}
                with patch('renew.gui_lock_path', return_value=path), patch('renew.bridge_request', return_value=response) as request:
                    with monitor_guard(cfg):
                        pass
                    self.assertEqual(request.call_count, 1)
                    self.assertEqual(request.call_args.args[1], 'GET')
                    response['inode'] += 1
                    with self.assertRaises(KeeperError):
                        with monitor_guard(cfg):
                            self.fail('wrong desktop must never start')

    def test_worker_retains_parent_lease_until_it_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'desktop.lock'
            child = None
            try:
                with process_lock(path, 0.1) as fd:
                    child = subprocess.Popen([sys.executable, '-c', 'import sys; print("ready",flush=True); sys.stdin.read()'],
                                             pass_fds=(fd,), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                    self.assertEqual(child.stdout.readline().strip(), 'ready')
                with self.assertRaises(KeeperError):
                    with process_lock(path, 0.01):
                        self.fail('parent close must not unlock a live worker')
                child.communicate('', timeout=5)
                with process_lock(path, 0.1):
                    pass
            finally:
                if child and child.poll() is None:
                    child.kill()
                    child.communicate()

    def test_selected_profile_is_independent_of_agent_environment(self):
        with patch.dict(os.environ, {'WECOM_CLI_CONFIG_DIR':'/wrong/inherited/profile'}):
            self.assertNotIn('WECOM_CLI_CONFIG_DIR', cli_environment({}))
            self.assertEqual(cli_environment({'cli_config_dir':'/selected/profile'})['WECOM_CLI_CONFIG_DIR'], '/selected/profile')
            self.assertEqual(os.environ['WECOM_CLI_CONFIG_DIR'], '/wrong/inherited/profile')

    def test_profile_inventory_uses_only_official_read_commands(self):
        calls = []
        def run(args, **kwargs):
            calls.append((args[1:], kwargs['env'].get('WECOM_CLI_CONFIG_DIR')))
            if args[1:] == ['--version']:
                output = 'wecom-cli 1.3.0'
            elif args[1:] == ['auth','show','--status']:
                output = 'authorized' if kwargs['env'].get('WECOM_CLI_CONFIG_DIR') is None else 'unauthorized'
            elif args[1:] == ['identity','whoami']:
                output = '{"extra_identity_context":"private fixture"}'
            else:
                self.fail('unexpected CLI operation')
            return subprocess.CompletedProcess(args,0,output,'')
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'profiles.json'
            with patch.dict(os.environ, {'WECOM_CLI_CONFIG_DIR':'/wrong/inherited'}):
                result = profiles.inspect_profiles('fixture', ['/known/secondary'], report, run=run)
            self.assertEqual(result['authorized_profiles'], 1)
            self.assertFalse(result['target_selected'])
            self.assertNotIn('private fixture', json.dumps(result))
            data = json.loads(report.read_text())
            self.assertEqual(data['profiles'][0]['cli_config_dir'], None)
            self.assertEqual(data['profiles'][1]['status'], 'unauthorized')
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            self.assertEqual(calls[-1][1], '/known/secondary')
            with self.assertRaises(FileExistsError):
                profiles.inspect_profiles('fixture', [], report, run=run)

    def test_onboarding_keeps_business_org_and_profile_without_activating_switch(self):
        value = {'bot_chat_name':'test','organization_name':'org B','cli_bot_id':'fixture',
                 'authorization_url':'https://work.weixin.qq.com/ai/aiHelper/authorizationList?aibotid=123&str_aibotid=fixture',
                 'target_rows':['搜索与获取文档内容'], 'cli_config_dir':'/private/second-bot'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            onboard.configure(value,path,'Darwin')
            cfg=json.loads(path.read_text())
            self.assertEqual(cfg['expected_organization'],'org B')
            self.assertEqual(cfg['cli_config_dir'],'/private/second-bot')
            self.assertNotIn('organization_navigation',cfg)
