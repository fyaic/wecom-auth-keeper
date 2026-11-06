import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keeper_common import KeeperError
from keeper_organization import org_visible, ensure_organization


def win_with(texts, frame=(0, 0, 960, 640)):
    return {"AXRole": "AXWindow", "frame": frame,
            "AXChildren": [{"AXRole": "AXStaticText", "AXTitle": t, "frame": (100, 100, 50, 20)} for t in texts]}


class FakeAXModule:
    """Duck-typed keeper_ax module over dict nodes."""

    def __init__(self, windows):
        self.windows = windows

    def application(self):
        return None, {"AXWindows": self.windows}

    def ax_get(self, node, attr):
        return node.get(attr) if isinstance(node, dict) else None

    def frame(self, node):
        return node.get("frame") if isinstance(node, dict) else None


def fake_ax(windows):
    return FakeAXModule(windows)


class FakeEngine:
    def __init__(self, cfg, windows):
        self.cfg = cfg
        self.ax = fake_ax(windows)
        self.sleeps = 0

    def sleep(self, _s):
        self.sleeps += 1

    def wait(self, read, accept, error, timeout=20):
        value = read()
        if accept(value):
            return value
        raise KeeperError(error, "timed out")


CFG = {"organization_name": "深圳市嘀嗒嘀物流科技有限公司", "organization_markers": ["装柜提醒bot"]}


class OrgVisibleTests(unittest.TestCase):
    def test_marker_visible(self):
        ax = fake_ax([win_with(["装柜提醒bot", "闲聊"])])
        self.assertTrue(org_visible(ax, ax.application()[1], CFG))

    def test_other_org_not_visible(self):
        ax = fake_ax([win_with(["弗忧智能聊天", "别的组织"])])
        self.assertFalse(org_visible(ax, ax.application()[1], CFG))

    def test_unconfigured_skips_check(self):
        ax = fake_ax([win_with(["随便什么"])])
        self.assertTrue(org_visible(ax, ax.application()[1], {}))


class EnsureTests(unittest.TestCase):
    def test_no_switch_when_visible(self):
        engine = FakeEngine(CFG, [win_with(["装柜提醒bot"])])
        result = ensure_organization(engine, None)
        self.assertEqual(result, {"switched": False})
        self.assertEqual(engine.sleeps, 0)

    def test_unconfigured_noop(self):
        engine = FakeEngine({}, [win_with(["任何内容"])])
        self.assertEqual(ensure_organization(engine, None), {"switched": False})

    def test_switcher_missing_raises(self):
        # 目标组织不可见，且窗口里没有头像按钮 → 明确报错而不是乱点
        engine = FakeEngine(CFG, [win_with(["弗忧的内容"])])
        with self.assertRaises(KeeperError) as ctx:
            ensure_organization(engine, None)
        self.assertIn("Avatar/org button not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
