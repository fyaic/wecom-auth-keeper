#!/usr/bin/env python3
"""Check archived handout/ZIP bytes and bundled files; no GUI or network access."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'release.json').read_text(encoding='utf-8'))
    artifacts = manifest['artifacts']
    if not artifacts:
        raise ValueError('No archived artifacts')
    for name, info in artifacts.items():
        if not name or name != Path(name).name or name in {'.', '..'} or '\\' in name:
            raise ValueError('Invalid artifact name')
        data = (directory / name).read_bytes()
        if len(data) != info['bytes'] or hashlib.sha256(data).hexdigest() != info['sha256']:
            raise ValueError('Artifact mismatch: ' + name)
        if name.endswith('.zip'):
            with zipfile.ZipFile(directory / name) as archive:
                names = archive.namelist()
                if len(names) != len(set(names)) or archive.testzip() is not None:
                    raise ValueError('ZIP integrity failure')
                prefix = 'wecom-auth-keeper/'
                bundled = json.loads(archive.read(prefix + 'MANIFEST.json'))
                if bundled['source_commit'] != manifest['zip_source_commit']:
                    raise ValueError('Unexpected ZIP source commit')
                expected = {prefix + 'MANIFEST.json'}
                for path, digest in bundled['files'].items():
                    pure = PurePosixPath(path)
                    if (pure.is_absolute() or '\\' in path
                            or any(part in ('', '.', '..') for part in path.split('/'))):
                        raise ValueError('Unsafe bundled path')
                    member = prefix + path
                    expected.add(member)
                    if hashlib.sha256(archive.read(member)).hexdigest() != digest:
                        raise ValueError('Bundled file mismatch: ' + path)
                if set(names) != expected:
                    raise ValueError('Unexpected ZIP entries')
    return len(artifacts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        count = verify(args.directory)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)
    print(json.dumps({'ok': True, 'artifacts': count, 'publisher_authenticated': False,
                      'device_acceptance_tested': False}))
