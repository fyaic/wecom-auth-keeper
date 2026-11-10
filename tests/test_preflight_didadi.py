import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from keeper_common import KeeperError
from preflight_didadi import check_fields, check_paths


def base_cfg():
    return {
        "bot_chat_name": "装柜提醒bot",
        "aibotid": "1234567890",
        "str_aibotid": "aibNIF3gzZPv1vFefOO9BgLY1u4TzaL0W5Y",
        "target_rows": ["搜索与获取文档内容", "新建与编辑文档", "搜索企业成员"],
        "venv_python": sys.executable,
        "state_file": str(self_dir() / "state.json"),
        "log_file": str(self_dir() / "run.log"),
    }


def self_dir():
    import tempfile
    return Path(tempfile.mkdtemp(prefix="preflight-test-"))


class PreflightFieldTests(unittest.TestCase):
    def test_valid_fields(self):
        report = check_fields(base_cfg())
        self.assertEqual(report["fields"], "ok")
        self.assertEqual(len(report["target_rows"]), 3)

    def test_placeholder_rejected(self):
        cfg = base_cfg()
        cfg["aibotid"] = "<机器人管理权限页链接里的 aibotid>"
        with self.assertRaises(KeeperError) as ctx:
            check_fields(cfg)
        self.assertIn("placeholder:aibotid", str(ctx.exception))

    def test_non_numeric_aibotid_rejected(self):
        cfg = base_cfg()
        cfg["aibotid"] = "aibNIF3gzZPv1vFefOO9BgLY1u4TzaL0W5Y"
        with self.assertRaises(KeeperError):
            check_fields(cfg)

    def test_str_aibotid_prefix_rejected(self):
        cfg = base_cfg()
        cfg["str_aibotid"] = "wobO-mCAAA..."
        with self.assertRaises(KeeperError):
            check_fields(cfg)

    def test_unknown_capability_rejected(self):
        cfg = base_cfg()
        cfg["target_rows"] = ["发射火箭"]
        with self.assertRaises(KeeperError) as ctx:
            check_fields(cfg)
        self.assertIn("capability catalog", str(ctx.exception))

    def test_paths_ok(self):
        cfg = base_cfg()
        report = check_paths(cfg)
        self.assertEqual(report["paths"], "ok")


class PreflightCliIdentityTests(unittest.TestCase):
    def test_bot_mismatch_detected(self):
        import preflight_didadi as pf

        class FakeResult:
            stdout = "Status: authorized\nBot ID: aibSOMEOTHERBOT0000000000000000\n"
            returncode = 0

        original = subprocess.run
        subprocess.run = lambda *a, **k: FakeResult()
        try:
            cfg = base_cfg()
            with self.assertRaises(KeeperError) as ctx:
                pf.check_cli_identity(cfg, "/tmp/nowhere")
            self.assertIn("refusing to renew another bot", str(ctx.exception))
        finally:
            subprocess.run = original


if __name__ == "__main__":
    unittest.main()
