"""End-to-end shell/CLI boundaries with a local fake CLI, never WeCom."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProcessTests(unittest.TestCase):
    def test_shell_wrappers_return_json_and_failure_status(self):
        with tempfile.TemporaryDirectory(prefix="keeper's fixture ") as temporary:
            directory = Path(temporary)
            binary = directory / "fake-cli"
            binary.write_text("#!" + sys.executable + '\nimport json, pathlib\nprint(pathlib.Path(__file__).with_name("response").read_text())\n')
            binary.chmod(0o700)
            config = directory / "config.json"
            config.write_text(json.dumps({
                'bot_chat_name':'fixture', 'aibotid':'123', 'str_aibotid':'fixture',
                'read_docid':"doc'with quotes", 'write_docid':"test'only", 'write_sheet':'sheet',
                'wecom_cli':str(binary), 'state_file':str(directory/'state.json'),
                'log_file':str(directory/'nested'/'log.jsonl'), 'notify_to':'',
            }))
            for response, success in (({'errcode':0},True),({'errcode':500},False),({},False)):
                (directory/'response').write_text(json.dumps(response))
                for entry in ('scripts/probe.sh','scripts/keepalive-run.sh'):
                    result = subprocess.run(['bash',str(ROOT/entry),'--config',str(config)],
                                            cwd=directory,capture_output=True,text=True,timeout=10)
                    self.assertEqual(result.returncode==0,success,(entry,result.stderr,result.stdout))
                    self.assertEqual(json.loads(result.stdout)['ok'],success)
            self.assertTrue((directory/'nested'/'log.jsonl').exists())

    def test_help_does_not_require_configuration_or_gui(self):
        result=subprocess.run([sys.executable,str(ROOT/'renew.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0)
        self.assertIn('--pre-renew',result.stdout)
