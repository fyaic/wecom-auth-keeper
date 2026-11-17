from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import plistlib
import subprocess
import sys
from unittest.mock import Mock, patch

import maintain
from keeper_common import KeeperError, atomic_json
from keeper_maintenance import policy, run_cycle
from test_keeper import Fixture, FakeAX


class MaintenanceTests(Fixture):
    def setup_cycle(self, rows=None):
        self.cfg['target_rows'] = rows or ['发送消息', '搜索与获取文档内容', '新建与编辑文档',
                                          '搜索与获取微盘文件内容', '上传与更新微盘文件',
                                          '搜索与获取邮件内容', '发送邮件']
        ax = FakeAX(self.cfg)
        engine = self.engine(ax)
        engine.close_window = Mock(return_value=({'ok': True, 'closed': True}, 0))
        self.wall = datetime.now()
        return ax, engine

    def cycle(self, ax, engine):
        return run_cycle(self.cfg, ax, engine=engine, now=lambda: self.wall)

    def scheduler(self):
        return json.loads(Path(self.cfg['state_file'] + '.maintenance.json').read_text())

    def test_mixed_capabilities_renew_only_due_and_restore_expired(self):
        ax, engine = self.setup_cycle()
        ax.dates['搜索与获取文档内容'] = datetime.now() + timedelta(days=3)
        ax.states['发送邮件'] = 'expired'
        ax.refresh()
        result, code = self.cycle(ax, engine)
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'renewed')
        self.assertFalse(result['business_verified'])
        self.assertEqual(result['rows']['发送邮件']['action'], 'restored')
        self.assertEqual(result['rows']['搜索与获取文档内容']['action'], 'not_due')
        self.assertFalse(any(n == '搜索与获取文档内容' for _, n in ax.clicks))
        self.assertFalse(any(t == '取消授权' and n == '发送邮件' for t, n in ax.clicks))
        self.assertEqual(sum(t == '授权' for t, _ in ax.clicks), 6)
        engine.close_window.assert_called_once()
        self.assertFalse(result['pending_recovery'])

    def test_far_future_permissions_are_checked_and_closed_without_revoking(self):
        ax, engine = self.setup_cycle(['发送消息'])
        ax.dates['发送消息'] = datetime.now() + timedelta(days=6)
        ax.refresh()
        result, code = self.cycle(ax, engine)
        self.assertEqual((code, result['status']), (0, 'healthy'))
        self.assertEqual(ax.clicks, [])
        engine.close_window.assert_called_once()

    def test_cooldown_is_per_permission_not_whole_bot(self):
        ax, engine = self.setup_cycle(['发送消息', '发送邮件'])
        self.cfg['maintenance'] = {'within_hours': 168}
        self.cycle(ax, engine)
        prior = len(ax.clicks)
        self.wall += timedelta(minutes=10)
        # Another permission's expiry changes externally; it may now be due.
        ax.dates['发送邮件'] = datetime.now() + timedelta(hours=1)
        ax.refresh()
        result, code = self.cycle(ax, engine)
        self.assertEqual(code, 0)
        self.assertEqual(result['rows']['发送消息']['action'], 'cooldown')
        self.assertEqual(result['rows']['发送邮件']['action'], 'pre_renewed')
        self.assertTrue(all(n == '发送邮件' for _, n in ax.clicks[prior:]))

    def test_partial_failure_persists_first_row_and_recovers_second_before_more_revokes(self):
        ax, engine = self.setup_cycle(['发送消息', '发送邮件', '搜索与获取微盘文件内容'])
        original = ax.click
        def fail_mail(el, window):
            ax.fail_grant = el.get('_row') == '发送邮件'
            return original(el, window)
        with patch.object(ax, 'click', side_effect=fail_mail):
            result, code = self.cycle(ax, engine)
        self.assertEqual(code, 2)
        self.assertEqual(result['rows']['发送消息']['action'], 'pre_renewed')
        self.assertTrue(engine.journal.exists())
        self.assertIn('expiry', self.scheduler()['permissions']['发送消息'])
        self.assertFalse(any(n == '搜索与获取微盘文件内容' for _, n in ax.clicks))
        prior = len(ax.clicks)
        ax.fail_grant = False
        self.wall += timedelta(minutes=6)
        result, code = self.cycle(ax, engine)
        self.assertEqual(code, 0)
        self.assertFalse(engine.journal.exists())
        self.assertEqual(result['rows']['发送邮件']['action'], 'reconciled')
        self.assertFalse(any(t == '取消授权' and n in {'发送消息','发送邮件'} for t,n in ax.clicks[prior:]))

    def test_crash_after_grant_is_reconciled_without_duplicate_revocation(self):
        ax, engine = self.setup_cycle(['发送消息'])
        self.cfg['maintenance'] = {'within_hours': 168}
        original = engine.pre_renew
        def crash(*args):
            original(*args)
            raise KeyboardInterrupt()
        with patch.object(engine, 'pre_renew', side_effect=crash):
            with self.assertRaises(KeyboardInterrupt): self.cycle(ax, engine)
        self.assertFalse(engine.journal.exists())
        self.assertIn('intent', self.scheduler()['permissions']['发送消息'])
        prior = len(ax.clicks)
        result, code = self.cycle(ax, engine)
        self.assertEqual(code, 0)
        self.assertEqual(result['rows']['发送消息']['action'], 'reconciled')
        self.assertEqual(len(ax.clicks), prior)

    def test_unresolved_intent_does_not_issue_another_revocation(self):
        ax, engine = self.setup_cycle(['发送消息'])
        with patch.object(engine, 'pre_renew', side_effect=RuntimeError('private')):
            self.assertEqual(self.cycle(ax, engine)[1], 2)
        self.wall += timedelta(minutes=6)
        result, code = self.cycle(ax, engine)
        self.assertEqual(result['error'], 'action_outcome_unknown')
        self.assertEqual(ax.clicks, [])
        self.assertNotIn('private', json.dumps(result))

    def test_failure_backs_off_without_opening_or_closing_any_window(self):
        ax, engine = self.setup_cycle(['发送消息'])
        with patch.object(engine, 'open', side_effect=KeeperError('page_not_open','missing')):
            self.cycle(ax, engine)
        engine.close_window.reset_mock()
        with patch.object(engine, 'open') as opened:
            result, code = self.cycle(ax, engine)
        self.assertEqual((code, result['status']), (2, 'backoff'))
        opened.assert_not_called()
        engine.close_window.assert_not_called()

    def test_cleanup_failure_preserves_renewal_evidence(self):
        ax, engine = self.setup_cycle(['发送消息'])
        engine.close_window.side_effect = RuntimeError('private-url')
        result, code = self.cycle(ax, engine)
        self.assertEqual((code, result['status']), (2, 'cleanup_failed'))
        self.assertEqual(result['rows']['发送消息']['action'], 'pre_renewed')
        self.assertNotIn('private-url', json.dumps(result))
        self.assertIn('expiry', self.scheduler()['permissions']['发送消息'])

    def test_wrong_bot_or_malformed_schedule_refuses_ui(self):
        ax, engine = self.setup_cycle(['发送消息'])
        path = Path(self.cfg['state_file'] + '.maintenance.json')
        for value in ({'identity':'wrong'}, []):
            atomic_json(path, value)
            with patch.object(engine,'open') as opened:
                with self.assertRaises(KeeperError): self.cycle(ax, engine)
            opened.assert_not_called()

    def test_policy_rejects_unknown_types_and_interval_longer_than_horizon(self):
        for value in ({'close_window':'false'}, {'within_hours':False}, {'within_hours':0},
                      {'within_hours':float('nan')}, {'interval_seconds':1},
                      {'interval_seconds':60.5}, {'within_hours':1,'interval_seconds':3600}, {'typo':1}, []):
            with self.assertRaises(KeeperError): policy({'maintenance':value})
        self.assertEqual(policy({})['within_hours'], 24)

    def test_close_can_be_explicitly_disabled(self):
        ax, engine = self.setup_cycle(['发送消息'])
        self.cfg['maintenance'] = {'close_window':False}
        self.cycle(ax, engine)
        engine.close_window.assert_not_called()

    def test_launchagent_uses_argument_array_and_configured_interval(self):
        self.cfg['venv_python'] = sys.executable
        self.cfg['maintenance'] = {'interval_seconds':1800,'within_hours':12}
        self.cfg['_config_path'] = str(self.root / "config with 'quotes.json")
        out = self.root / 'job.plist'
        result = maintain.write_launchagent(self.cfg,out)
        data = plistlib.loads(out.read_bytes())
        self.assertFalse(result['installed'])
        self.assertEqual(data['StartInterval'], 1800)
        self.assertTrue(data['RunAtLoad'])
        self.assertEqual(data['ProgramArguments'][-1], self.cfg['_config_path'])
        self.assertIn('maintain.py',data['ProgramArguments'][1])
        with self.assertRaises(KeeperError): maintain.write_launchagent(self.cfg,out)

    def test_schedule_cannot_overwrite_config(self):
        for path in (self.cfg['state_file'] + '.maintenance.json', self.cfg['log_file'] + '.maintenance.log'):
            self.cfg['_config_path'] = path
            with self.assertRaises(KeeperError): maintain.validate_destinations(self.cfg)

    def test_timeout_is_non_success_and_attempts_separate_cleanup(self):
        self.cfg['venv_python'] = sys.executable
        runner = Mock(side_effect=[subprocess.TimeoutExpired(['worker'],1),
                                  subprocess.CompletedProcess([],0,'{"ok":true,"closed":true}','')])
        result, code = maintain.supervise(self.cfg, run=runner)
        self.assertEqual((code,result['status']), (2,'timeout'))
        self.assertTrue(result['cleanup']['ok'])
        self.assertIn('--worker',runner.call_args_list[0].args[0])
        self.assertIn('--close-window',runner.call_args_list[1].args[0])

    def test_supervisor_rejects_contradictory_success_or_wrong_mode(self):
        self.cfg['venv_python'] = sys.executable
        for exit_code, payload in [(2, {'ok':True,'mode':'maintenance'}), (0, {'ok':True,'mode':'doctor'}),
                                   (0, {'ok':False}), (0, [])]:
            runner=Mock(return_value=subprocess.CompletedProcess([],exit_code,json.dumps(payload),''))
            result, code = maintain.supervise(self.cfg,run=runner)
            self.assertEqual(code,2)
            self.assertFalse(result['ok'])

    def test_discovery_needs_no_account_or_gui(self):
        result=subprocess.run([sys.executable,str(Path(maintain.__file__)),'--list-capabilities'],
                              capture_output=True,text=True,check=True)
        groups=json.loads(result.stdout)['capability_groups']
        self.assertEqual(groups['mail'], ['搜索与获取邮件内容','发送邮件'])
        self.assertIn('上传与更新微盘文件',groups['disk'])



class NotDueGateTests(MaintenanceTests):
    """2026-11-17 未到期先决门：远期+新鲜 ⇒ 零 GUI 跳过，状态零副作用。"""

    def _seed_state(self, engine, *, failures=0, days=6, checked_hours_ago=1, rows=None):
        rows = self.cfg['target_rows'] if rows is None else rows
        permissions = {
            name: {'expiry': (datetime.now() + timedelta(days=days)).isoformat(timespec='minutes'),
                   'checked_at': (datetime.now() - timedelta(hours=checked_hours_ago)).isoformat(timespec='seconds'),
                   'next_allowed_at': 0}
            for name in rows}
        atomic_json(Path(self.cfg['state_file'] + '.maintenance.json'),
                    {'version': 1, 'identity': engine.identity, 'permissions': permissions,
                     'failures': failures, 'next_retry_at': 0})
        return permissions

    def test_not_due_skips_gui_and_preserves_failure_state(self):
        ax, engine = self.setup_cycle(rows=['发送消息'])
        engine.open = Mock(return_value=None)
        engine.close_window = Mock(return_value=({'ok': True, 'closed': True}, 0))
        self._seed_state(engine, failures=5)
        result, code = self.cycle(ax, engine)
        self.assertEqual((code, result['status']), (0, 'not_due_skipped'))
        engine.open.assert_not_called()
        engine.close_window.assert_not_called()
        state = self.scheduler()
        self.assertEqual(state['failures'], 5)  # 跳过不抹也不加失败账

    def test_missing_expiry_record_navigates(self):
        ax, engine = self.setup_cycle(rows=['发送消息'])
        opened = Mock(return_value=None)
        engine.open = opened
        self._seed_state(engine, rows=[])  # 目标行无记录
        self.cycle(ax, engine)
        opened.assert_called()

    def test_within_window_navigates(self):
        ax, engine = self.setup_cycle(rows=['发送消息'])
        opened = Mock(return_value=None)
        engine.open = opened
        self._seed_state(engine, days=0.5)
        self.cycle(ax, engine)
        opened.assert_called()

    def test_stale_checked_at_navigates(self):
        ax, engine = self.setup_cycle(rows=['发送消息'])
        opened = Mock(return_value=None)
        engine.open = opened
        self._seed_state(engine, checked_hours_ago=30)
        self.cycle(ax, engine)
        opened.assert_called()

    def test_pending_journal_forces_navigation(self):
        ax, engine = self.setup_cycle(rows=['发送消息'])
        opened = Mock(return_value=None)
        engine.open = opened
        self._seed_state(engine)
        Path(self.cfg['state_file'] + '.pending.json').write_text('{}')
        self.cycle(ax, engine)
        opened.assert_called()

    def test_navigation_due_unit_matrix(self):
        from keeper_maintenance import DEFAULT_POLICY, navigation_due
        state = {'permissions': {
            'a': {'expiry': '2026-11-23T17:41', 'checked_at': '2026-11-17T12:00:00'}}}
        rows = ['a']
        far = lambda: datetime(2026, 11, 17, 13, 0, 0)
        self.assertFalse(navigation_due(state, DEFAULT_POLICY, rows, far))
        self.assertTrue(navigation_due(state, DEFAULT_POLICY, rows,
                                       lambda: datetime(2026, 11, 22, 18, 0, 0)))
        self.assertTrue(navigation_due(state, DEFAULT_POLICY, rows,
                                       lambda: datetime(2026, 11, 18, 13, 0, 1)))  # 陈旧
        self.assertTrue(navigation_due({'permissions': {}}, DEFAULT_POLICY, rows, far))
        self.assertTrue(navigation_due(state, DEFAULT_POLICY, rows, far, pending=True))


class StalePolicyTests(Fixture):
    def test_default_and_bounds(self):
        from keeper_maintenance import DEFAULT_POLICY, policy
        self.assertEqual(DEFAULT_POLICY['stale_after_hours'], 24)
        self.assertEqual(policy({})['stale_after_hours'], 24)
        self.assertEqual(policy({'maintenance': {'stale_after_hours': 48}})['stale_after_hours'], 48)
        for bad in (0, 169, 24.5, True):
            with self.assertRaises(KeeperError):
                policy({'maintenance': {'stale_after_hours': bad}})
