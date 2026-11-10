"""Exercise the release artifact, including generated aliases and reader handoffs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bundle_build_review', SOURCE / 'delivery/build_bundle.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BundleBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='keeper-bundle-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.files = {
            'LICENSE': b'fixture\n',
            'AGENTS.md': b'[runbook](delivery/AGENT-RUNBOOK.md)\n',
            'delivery/START-HERE.md': ('[evidence](VALIDATION.md#evidence)\n'
                                      '[spaces](<权限%20说明.md>)\n'
                                      '```text\n[example](not-a-real-link.md)\n```\n').encode(),
            'delivery/USER-GUIDE.txt': '中文使用说明\n解压到固定目录。\n'.encode(),
            'delivery/AGENT-RUNBOOK.md': ('[entry](../AGENTS.md)\n[guide][intro]\n'
                                         '[intro]: <START-HERE.md> "介绍"\n'
                                         '[external](https://example.test/docs#section)\n').encode(),
            'delivery/VALIDATION.md': b'# evidence\n',
            'delivery/权限 说明.md': '说明\n'.encode(),
        }
        for name, data in self.files.items():
            p = self.source / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        self.git('init', '-q')
        self.commit()
        self.root_patch = patch.object(builder, 'ROOT', self.source)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.files_patch = patch.object(builder, 'FILES', list(self.files))
        self.files_patch.start()
        self.addCleanup(self.files_patch.stop)
        self.output = self.base / 'release' / 'keeper.zip'

    def git(self, *args):
        return subprocess.check_output(['git', '-c', 'user.name=Release Fixture',
                                        '-c', 'user.email=release@example.test', '-c', 'commit.gpgsign=false',
                                        '-c', 'core.hooksPath=/dev/null', *args],
                                       cwd=self.source, stderr=subprocess.PIPE)

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'Fixture source')

    def test_generated_reader_aliases_links_manifest_and_external_handoffs(self):
        report = builder.build(self.output)
        with zipfile.ZipFile(self.output) as z:
            root = 'wecom-auth-keeper/'
            start = z.read(root + 'START-HERE.md').decode()
            agent = z.read(root + '给Agent.md').decode()
            self.assertIn('(delivery/VALIDATION.md#evidence)', start)
            self.assertIn('(<delivery/%E6%9D%83%E9%99%90%20%E8%AF%B4%E6%98%8E.md>)', start)
            self.assertIn('[example](not-a-real-link.md)', start)
            self.assertIn('(AGENTS.md)', agent)
            self.assertIn('[intro]: <delivery/START-HERE.md> "介绍"', agent)
            self.assertIn('(https://example.test/docs#section)', agent)
            self.assertEqual(z.read(root + '给使用者.txt'), self.files['delivery/USER-GUIDE.txt'])
            manifest = json.loads(z.read(root + 'MANIFEST.json'))
            self.assertEqual(manifest['edition'], 'macos-agent-installer')
            self.assertEqual(manifest['support'], {'macos': 'requires-device-acceptance',
                                                   'windows': 'no-automation-backend'})
            self.assertEqual(manifest['source_commit'], self.git('rev-parse', 'HEAD').decode().strip())
            self.assertEqual(set(z.namelist()), {root + n for n in manifest['files']} | {root + 'MANIFEST.json'})
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256(z.read(root + name)).hexdigest(), digest)
        self.assertEqual((self.output.parent / '给使用者.txt').read_bytes(), self.files['delivery/USER-GUIDE.txt'])
        handoff = (self.output.parent / '给Agent.md').read_text()
        self.assertIn('keeper.zip.sha256', handoff)
        self.assertIn('AGENTS.md', handoff)
        self.assertNotIn('](', handoff)
        self.assertEqual(report['sha256'], hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertEqual(self.output.with_suffix('.zip.sha256').read_text(), report['sha256'] + '  keeper.zip\n')
        self.assertEqual({p.name for p in self.output.parent.iterdir()},
                         {'keeper.zip', 'keeper.zip.sha256', '给使用者.txt', '给Agent.md'})

    def test_missing_link_fails_before_any_release_file_is_written(self):
        (self.source / 'delivery/START-HERE.md').write_text('[missing](MISSING.md)\n')
        self.commit()
        with self.assertRaisesRegex(ValueError, 'missing bundled link'):
            builder.build(self.output)
        self.assertFalse(self.output.parent.exists())

    def test_link_escape_and_absolute_file_links_fail_before_publication(self):
        for target in ['../../outside.md', '%2e%2e/%2e%2e/outside.md', '/outside.md', 'file:///outside.md', 'C:\\outside.md']:
            with self.subTest(target=target):
                (self.source / 'delivery/START-HERE.md').write_text(f'[bad]({target})\n')
                self.commit()
                with self.assertRaises(ValueError):
                    builder.build(self.output)
                self.assertFalse(self.output.parent.exists())

    def test_missing_committed_source_is_not_replaced_by_untracked_file(self):
        (self.source / 'untracked.txt').write_text('not committed')
        with patch.object(builder, 'FILES', [*self.files, 'untracked.txt']):
            with self.assertRaisesRegex(ValueError, 'missing from commit'):
                builder.build(self.output)
        self.assertFalse(self.output.parent.exists())

    def test_missing_working_source_is_rejected(self):
        (self.source / 'LICENSE').unlink()
        with self.assertRaises(FileNotFoundError):
            builder.build(self.output)
        self.assertFalse(self.output.parent.exists())

    def test_allowlist_path_escape_is_rejected_before_git_read(self):
        for name in ['../outside', '/outside', 'delivery/../../outside', 'delivery\\outside']:
            with self.subTest(name=name), patch.object(builder, 'FILES', [name]):
                with self.assertRaisesRegex(ValueError, 'Unsafe release path'):
                    builder.build(self.output)
                self.assertFalse(self.output.parent.exists())

    def test_reserved_manifest_and_duplicate_sources_are_rejected(self):
        for entries in [['MANIFEST.json'], ['LICENSE', 'LICENSE']]:
            with self.subTest(entries=entries), patch.object(builder, 'FILES', entries):
                with self.assertRaisesRegex(ValueError, 'Reserved release path|Duplicate release path'):
                    builder.build(self.output)
                self.assertFalse(self.output.parent.exists())

    def test_uncommitted_changes_are_not_packaged(self):
        (self.source / 'LICENSE').write_text('modified')
        with self.assertRaisesRegex(ValueError, 'Commit release changes'):
            builder.build(self.output)
        self.assertFalse(self.output.parent.exists())

    def test_private_untracked_files_are_excluded(self):
        (self.source / 'config.json').write_text('{"private":true}')
        (self.source / 'run.log').write_text('private log')
        builder.build(self.output)
        with zipfile.ZipFile(self.output) as z:
            self.assertNotIn('wecom-auth-keeper/config.json', z.namelist())
            self.assertNotIn('wecom-auth-keeper/run.log', z.namelist())

    def test_all_four_existing_artifacts_are_preserved(self):
        self.output.parent.mkdir()
        for name in ['keeper.zip', 'keeper.zip.sha256', '给使用者.txt', '给Agent.md']:
            with self.subTest(name=name):
                p = self.output.parent / name
                p.write_bytes(b'existing')
                with self.assertRaises(FileExistsError):
                    builder.build(self.output)
                self.assertEqual(p.read_bytes(), b'existing')
                self.assertEqual(list(self.output.parent.iterdir()), [p])
                p.unlink()

    def test_broken_symlink_is_an_existing_artifact(self):
        self.output.parent.mkdir()
        p = self.output.parent / '给Agent.md'
        p.symlink_to(self.base / 'absent')
        with self.assertRaises(FileExistsError):
            builder.build(self.output)
        self.assertTrue(p.is_symlink())
        self.assertFalse(self.output.exists())

    def test_write_race_preserves_existing_file_and_removes_only_own_outputs(self):
        original_open = Path.open
        checksum = self.output.with_suffix('.zip.sha256')

        def racing_open(path, mode='r', *args, **kwargs):
            if path == checksum and mode == 'xb':
                with original_open(path, 'wb') as stream:
                    stream.write(b'concurrent release')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(Path, 'open', racing_open):
            with self.assertRaises(FileExistsError):
                builder.build(self.output)
        self.assertEqual(checksum.read_bytes(), b'concurrent release')
        self.assertEqual(list(self.output.parent.iterdir()), [checksum])

    def test_archive_cannot_alias_external_guide(self):
        with self.assertRaisesRegex(ValueError, 'must be distinct'):
            builder.build(self.output.parent / '给使用者.txt')
        self.assertFalse(self.output.parent.exists())


if __name__ == '__main__':
    unittest.main()
