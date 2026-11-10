from unittest.mock import Mock
from test_delivery import module
from test_keeper import Fixture,FakeAX
from keeper_common import KeeperError
g=module('grant_initial')
class InitialGrantTests(Fixture):
    def test_first_grant_does_not_revoke_or_claim_renewal(self):
        ax=FakeAX(self.cfg,{n:'expired' for n in self.cfg['target_rows']})
        engine=self.engine(ax);engine.close_window=Mock(return_value=({'closed':True},0))
        result,code=g.grant(self.cfg,ax,engine=engine)
        self.assertEqual(code,0);self.assertFalse(result['renewal_verified'])
        self.assertEqual(result['mode'],'initial-grant')
        self.assertTrue(all(text=='授权' for text,_ in ax.clicks))
        self.assertEqual(len(ax.clicks),len(self.cfg['target_rows']))
        engine.close_window.assert_called_once()
    def test_healthy_first_use_is_idempotent_and_cleanup_runs(self):
        ax=FakeAX(self.cfg);engine=self.engine(ax)
        engine.close_window=Mock(return_value=({'closed':True},0))
        result,code=g.grant(self.cfg,ax,engine=engine)
        self.assertEqual(code,0);self.assertEqual(ax.clicks,[])
        self.assertTrue(result['cleanup']['closed'])
    def test_coordination_failure_preserved_and_cleanup_attempted(self):
        engine=Mock();engine.run.side_effect=KeeperError('desktop_coordination_required','busy')
        engine.close_window.return_value=({'closed':False},0)
        with self.assertRaises(KeeperError) as caught:g.grant(self.cfg,None,engine=engine)
        self.assertEqual(caught.exception.code,'desktop_coordination_required')
        engine.close_window.assert_called_once()
    def test_cleanup_failure_cannot_report_success(self):
        engine=Mock();engine.run.return_value=({'ok':True},0)
        engine.close_window.side_effect=RuntimeError()
        with self.assertRaises(KeeperError):g.grant(self.cfg,None,engine=engine)
