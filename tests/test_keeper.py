import contextlib
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import keepalive
import probe
import renew
from keeper_common import KeeperError, atomic_json, load_config, process_lock


def node(role, text='', x=100, y=100, children=None, **attributes):
    return {'AXRole': role, 'AXTitle': text, '_frame': (x, y, 120, 20),
            'AXChildren': children or [], **attributes}


class FakeAX:
    def __init__(self, cfg, states=None):
        self.cfg = cfg
        self.states = states or {n: 'authorized' for n in cfg['target_rows']}
        self.dates = {n: datetime.now() + timedelta(hours=4) for n in cfg['target_rows']}
        self.window = node('AXWindow', _frame=(0, 0, 900, 800))
        self.page = node('AXWebArea', AXURL='https://work.weixin.qq.com/ai/aiHelper/authorizationList?aibotid=123&str_aibotid=fixture')
        self.window['AXChildren'] = [self.page]
        self.app = node('AXApplication', AXWindows=[self.window])
        self.clicks = []
        self.fail_grant = False
        self.menu = None
        self.confirm = None
        self.refresh()

    def refresh(self):
        children = []
        for i, name in enumerate(self.cfg['target_rows']):
            y = 100 + i * 100
            children.append(node('AXStaticText', name, y=y))
            state = self.states[name]
            if state == 'authorized':
                children.extend([node('AXStaticText', '已授权', x=500, y=y+10, _row=name),
                                 node('AXStaticText', '有效期至 '+self.dates[name].strftime('%m/%d %H:%M'), x=500, y=y+35)])
            elif state == 'expired':
                children.append(node('AXButton', '授权', x=500, y=y+10, _row=name))
        if self.menu:
            children.append(node('AXStaticText', '取消授权', _row=self.menu))
        if self.confirm:
            children.append(node('AXButton', '取消授权', _row=self.confirm))
        self.page['AXChildren'] = children

    def ax_get(self, element, key): return element.get(key)
    def frame(self, element): return element.get('_frame')
    def application(self): return object(), self.app
    def activate(self, app): pass
    def click(self, element, window):
        name, text = element.get('_row'), element['AXTitle']
        self.clicks.append((text, name))
        if text == '已授权': self.menu = name
        elif text == '取消授权' and element['AXRole'] != 'AXButton':
            self.menu, self.confirm = None, name
        elif text == '取消授权':
            self.states[name] = 'expired'; self.confirm = None
        elif text == '授权' and not self.fail_grant:
            self.states[name] = 'authorized'; self.dates[name] = datetime.now() + timedelta(days=7)
        self.refresh()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = {'bot_chat_name':'fixture', 'aibotid':'123', 'str_aibotid':'fixture',
                    'target_rows':['新建与编辑文档','搜索与获取文档内容'],
                    'state_file':str(self.root/'state.json'), 'log_file':str(self.root/'run.log'),
                    'read_docid':'test-read', 'write_docid':'test-write', 'write_sheet':'test-sheet',
                    'bridge_send_link':False, 'bridge_monitor':False, 'probe_timeout':1,
                    'renew_timeout':1, 'lock_wait':0.1, '_config_path':str(self.root/'config.json')}
        self.now = 0
    def sleep(self, n): self.now += n
    def engine(self, ax): return renew.Renewal(self.cfg, ax, clock=lambda:self.now, sleep=self.sleep)
    def write_config(self):
        path = self.root/'config.json'; path.write_text(json.dumps(self.cfg)); return path


class StateTests(Fixture):
    def test_main_failure_is_nonzero_json_and_invalidates_cached_success(self):
        ax=FakeAX(self.cfg)
        engine=self.engine(ax)
        atomic_json(self.cfg['state_file'],{'ok':True})
        output=io.StringIO()
        with patch('renew.sys.platform','darwin'),patch.dict(sys.modules,{'keeper_ax':ax}), \
             patch('renew.Renewal',return_value=engine), \
             patch('renew.gui_lock_path',return_value=self.root/'gui.lock'), \
             patch.object(engine,'run',side_effect=KeeperError('rows_incomplete','Incomplete page')), \
             contextlib.redirect_stdout(output):
            code=renew.main(['--config',str(self.write_config()),'--renew','--existing-window'])
        self.assertEqual(code,2)
        self.assertFalse(json.loads(output.getvalue())['ok'])
        self.assertFalse(json.loads(Path(self.cfg['state_file']).read_text())['ok'])

    def test_neighbouring_unconfigured_permission_cannot_supply_status(self):
        ax=FakeAX(self.cfg);ax.states[self.cfg['target_rows'][0]]='loading';ax.refresh()
        ax.page['AXChildren'].extend([
            node('AXStaticText','发送邮件',y=130),
            node('AXButton','授权',x=500,y=140),
        ])
        row=self.engine(ax).read_rows(ax.window)[self.cfg['target_rows'][0]]
        self.assertEqual(row['status'],'unknown');self.assertIsNone(row['btn'])

    def test_pending_journal_for_other_bot_prevents_actions(self):
        ax=FakeAX(self.cfg);engine=self.engine(ax)
        atomic_json(engine.journal,{'identity':'another-bot','row':self.cfg['target_rows'][0],
                                    'expiry_before':datetime.now().isoformat()})
        with self.assertRaises(KeeperError):engine.run('renew',True)
        self.assertEqual(ax.clicks,[]);self.assertTrue(engine.journal.exists())

    def test_partial_row_is_unknown_not_authorized(self):
        ax=FakeAX(self.cfg); ax.states[self.cfg['target_rows'][0]]='loading'; ax.refresh()
        engine=self.engine(ax)
        self.assertEqual(engine.read_rows(ax.window)[self.cfg['target_rows'][0]]['status'],'unknown')
        with self.assertRaises(KeeperError): engine.run('check',True)
        self.assertEqual(ax.clicks,[])

    def test_expired_date_without_action_is_not_healthy(self):
        ax=FakeAX(self.cfg); ax.dates[self.cfg['target_rows'][0]]=datetime.now()-timedelta(days=1);ax.refresh()
        result,code=self.engine(ax).run('check',True)
        self.assertFalse(result['ok']);self.assertEqual(code,2)

    def test_renew_failure_raises_and_never_reports_success(self):
        ax=FakeAX(self.cfg,{n:'expired' for n in self.cfg['target_rows']});ax.fail_grant=True
        with self.assertRaises(KeeperError):self.engine(ax).run('renew',True)
        self.assertEqual(len(ax.clicks),3)

    def test_success_persists_post_renewal_expiry(self):
        ax=FakeAX(self.cfg,{n:'expired' for n in self.cfg['target_rows']})
        result,code=self.engine(ax).run('renew',True)
        saved=json.loads(Path(self.cfg['state_file']).read_text())
        self.assertEqual(code,0)
        for name in self.cfg['target_rows']:
            self.assertEqual(saved['rows'][name]['expiry'],result['rows'][name]['expiry'])
            self.assertGreater(datetime.fromisoformat(saved['rows'][name]['expiry']),datetime.now()+timedelta(days=6))

    def test_wrong_identity_does_not_click(self):
        ax=FakeAX(self.cfg);ax.page['AXURL']=ax.page['AXURL'].replace('123','456')
        with self.assertRaises(KeeperError):self.engine(ax).run('renew',True)
        self.assertEqual(ax.clicks,[])

    def test_duplicate_windows_fail_closed(self):
        ax=FakeAX(self.cfg);ax.app['AXWindows']=[ax.window,ax.window]
        with self.assertRaises(KeeperError):self.engine(ax).run('renew',True)
        self.assertEqual(ax.clicks,[])

    def test_pre_renew_extends_and_removes_journal(self):
        ax=FakeAX(self.cfg);engine=self.engine(ax)
        result,code=engine.run('pre-renew',True,24)
        self.assertEqual(code,0);self.assertFalse(engine.journal.exists())
        self.assertEqual(sum(text=='取消授权' for text,_ in ax.clicks),4)
        self.assertTrue(all(r['expiry']>r['expiry_before'] for r in result['rows'].values()))

    def test_pre_renew_skip_not_due(self):
        ax=FakeAX(self.cfg)
        result,code=self.engine(ax).run('pre-renew',True,1)
        self.assertEqual(code,0);self.assertEqual(ax.clicks,[])

    def test_failed_pre_renew_stops_second_row_and_saves_recovery(self):
        ax=FakeAX(self.cfg);ax.fail_grant=True;engine=self.engine(ax)
        with self.assertRaisesRegex(KeeperError,'pending recovery'):engine.run('pre-renew',True,24)
        self.assertTrue(engine.journal.exists())
        self.assertFalse(any(name==self.cfg['target_rows'][1] for _,name in ax.clicks))
        ax.fail_grant=False
        result,code=engine.run('renew',True)
        self.assertEqual(code,0);self.assertFalse(engine.journal.exists())
        self.assertEqual(ax.states[self.cfg['target_rows'][0]],'authorized')

    def test_check_never_sends_or_changes_monitor(self):
        self.cfg.update(bridge_send_link=True,bridge_monitor=True)
        ax=FakeAX(self.cfg)
        with patch('renew.bridge_request') as http:
            self.engine(ax).run('check',True)
        http.assert_not_called();self.assertEqual(ax.clicks,[])

    def test_negative_coordinates_are_not_rejected_by_row_parser(self):
        ax=FakeAX(self.cfg)
        for el in ax.page['AXChildren']:
            x,y,w,h=el['_frame'];el['_frame']=(x-1000,y-500,w,h)
        self.assertTrue(all(r['status']=='authorized' for r in self.engine(ax).read_rows(ax.window).values()))

    def test_expiry_new_year_and_invalid_date(self):
        now=datetime(2026,12,30)
        self.assertEqual(renew.parse_expiry('有效期至 1/3 10:00',now),datetime(2027,1,3,10))
        self.assertIsNone(renew.parse_expiry('有效期至 2/30 10:00',now))

    def test_url_host_and_both_ids_required(self):
        good='https://work.weixin.qq.com/ai/aiHelper/authorizationList?aibotid=123&str_aibotid=fixture'
        self.assertTrue(renew.target_url(good,self.cfg))
        for bad in (good.replace('https:','http:'),good.replace('work.weixin.qq.com','work.weixin.qq.com.evil.test'),good+'&aibotid=456',good.replace('fixture','other')):
            self.assertFalse(renew.target_url(bad,self.cfg))

    def test_monitor_restores_prior_mode_on_exception(self):
        self.cfg.update(bridge_monitor=True,bridge_url='http://localhost')
        with patch('renew.bridge_request',side_effect=[{'mode':'observe'},{'mode':'observe'},{'mode':'observe'}]) as http:
            with self.assertRaises(ValueError):
                with renew.monitor_guard(self.cfg):raise ValueError('test')
        self.assertEqual(http.call_args.args[-1],{'mode':'observe'})


class ProbeTests(Fixture):
    def test_noisy_or_missing_errcode_is_failure(self):
        for output in ('not json','{}','[]','{"errcode":false}'):
            with patch('probe.subprocess.run',return_value=subprocess.CompletedProcess([],0,output,'')):
                self.assertFalse(probe.call_cli('unused',[],1)['ok'])
    def test_nonzero_process_cannot_claim_success(self):
        with patch('probe.subprocess.run',return_value=subprocess.CompletedProcess([],1,'{"errcode":0}','')):
            self.assertFalse(probe.call_cli('unused',[],1)['ok'])
    def test_timeout_is_structured(self):
        with patch('probe.subprocess.run',side_effect=subprocess.TimeoutExpired('unused',1)):
            self.assertEqual(probe.call_cli('unused',[],1)['error'],'timeout')
    def test_expiry_retained_for_recovery(self):
        with patch('probe.subprocess.run',return_value=subprocess.CompletedProcess([],1,'{"errcode":850003}','secret')):
            self.assertEqual(probe.call_cli('unused',[],1)['errcode'],850003)
    def test_arguments_not_interpreted_as_code(self):
        self.cfg['write_docid']="$(touch /tmp/should-not-exist)'"
        with patch('probe.executable',return_value='fake-cli'),patch('probe.call_cli',return_value={'ok':True,'errcode':0}) as call:
            probe.run_probes(self.cfg)
        self.assertIn(self.cfg['write_docid'],call.call_args.args[1])


class KeepaliveTests(Fixture):
    def probes(self,read=0,write=0):
        return {'ok':read==write==0,'read':{'ok':read==0,'errcode':read},'write':{'ok':write==0,'errcode':write}}
    def test_network_failure_does_not_trigger_gui(self):
        with patch('keepalive.run_probes',return_value=self.probes(None,None)),patch('keepalive.recover') as action:
            result=keepalive.cycle(self.cfg)
        self.assertFalse(result['ok']);action.assert_not_called()
    def test_requires_api_and_gui_success(self):
        with patch('keepalive.run_probes',side_effect=[self.probes(850003,0),self.probes()]),patch('keepalive.recover',return_value={'ok':False}):
            self.assertFalse(keepalive.cycle(self.cfg)['ok'])
    def test_api_failure_after_gui_success_is_not_healthy(self):
        with patch('keepalive.run_probes',side_effect=[self.probes(850003,0),self.probes(0,500)]),patch('keepalive.recover',return_value={'ok':True}):
            self.assertFalse(keepalive.cycle(self.cfg)['ok'])
    def test_recovery_verified(self):
        with patch('keepalive.run_probes',side_effect=[self.probes(850003,0),self.probes()]),patch('keepalive.recover',return_value={'ok':True}):
            self.assertEqual(keepalive.cycle(self.cfg)['status'],'recovered')
    def test_notice_http_success_flag_required(self):
        self.cfg.update(notify_to='test',bridge_url='http://localhost')
        with patch('keepalive.bridge_request',return_value={'success':False}):
            with self.assertRaises(KeeperError):keepalive.notify(self.cfg,{'ok':False,'status':'probe_failed'})
        self.assertFalse(Path(self.cfg['log_file']+'.notice.json').exists())
    def test_notice_deduplicates_then_reports_recovery(self):
        self.cfg.update(notify_to='test',bridge_url='http://localhost')
        with patch('keepalive.bridge_request',return_value={'success':True}) as http:
            self.assertEqual(keepalive.notify(self.cfg,{'ok':False,'status':'probe_failed'}),'sent')
            self.assertEqual(keepalive.notify(self.cfg,{'ok':False,'status':'probe_failed'}),'deduplicated')
            self.assertEqual(keepalive.notify(self.cfg,{'ok':True,'status':'healthy'}),'sent')
        self.assertEqual(http.call_count,2)


class ConfigTests(Fixture):
    def test_state_cannot_overwrite_configuration(self):
        self.cfg['state_file']=str(self.root/'config.json')
        with self.assertRaises(KeeperError):load_config(self.write_config())

    def test_invalid_config_has_nonzero_single_json(self):
        path=self.root/'bad.json';path.write_text('{')
        for command in ('renew.py','probe.py','keepalive.py'):
            proc=subprocess.run([sys.executable,command,'--config',str(path)],capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0);self.assertFalse(json.loads(proc.stdout)['ok'])
    def test_relative_paths_anchor_config_directory(self):
        self.cfg['state_file']='state.json'
        self.assertEqual(Path(load_config(self.write_config())['state_file']), (self.root/'state.json').resolve())
    def test_placeholders_rejected(self):
        self.cfg['read_docid']='<placeholder>'
        with self.assertRaises(KeeperError):load_config(self.write_config(),probes=True)
    def test_bad_timeout_rejected(self):
        self.cfg['probe_timeout']=float('nan')
        with self.assertRaises(KeeperError):load_config(self.write_config())
    def test_atomic_file_private_and_complete(self):
        path=self.root/'nested'/'state.json';atomic_json(path,{'new':1})
        self.assertEqual(json.loads(path.read_text()),{'new':1});self.assertEqual(path.stat().st_mode&0o777,0o600)
    def test_lock_released_after_failure(self):
        path=self.root/'lock'
        with self.assertRaises(ValueError):
            with process_lock(path,0.01):raise ValueError('test')
        with process_lock(path,0.01):pass
    def test_lock_cannot_be_stolen_by_second_holder(self):
        with process_lock(self.root/'lock',0.01):
            with self.assertRaises(KeeperError):
                with process_lock(self.root/'lock',0.01):pass


if __name__=='__main__':unittest.main()
