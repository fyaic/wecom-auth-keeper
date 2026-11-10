#!/usr/bin/env python3
"""Build a clean source ZIP and reader handoffs from committed allowlisted files."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
from urllib.parse import quote, unquote, urlsplit, urlunsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['LICENSE', 'AGENTS.md', 'requirements-macos.txt', 'renew.py', 'maintain.py', 'keeper_ax.py',
         'keeper_common.py', 'keeper_navigation.py', 'keeper_organization.py', 'keeper_maintenance.py', 'keeper_accessibility.py',
         'keeper_capabilities.py', 'keeper_cleanup.py', 'config.maintenance.example.json',
         'keeper_bootstrap.py', 'delivery/prepare_entry.py', 'delivery/seed_entry.py', 'delivery/grant_initial.py', 'delivery/verify_entry.py', 'delivery/FIRST-RUN.md',
         'delivery/onboard.py', 'delivery/profiles.py', 'delivery/select_target.py', 'delivery/existing_entry.py', 'delivery/verify_bundle.py', 'delivery/gui.py', 'delivery/discover.py',
         'delivery/desktop_inspect.py', 'delivery/START-HERE.md', 'delivery/USER-GUIDE.txt', 'delivery/AGENT-RUNBOOK.md',
         'delivery/AGENT-INSTALL.md', 'delivery/BRIDGE-COORDINATION.md', 'delivery/DESIGN.md', 'delivery/VALIDATION.md', 'delivery/acceptance.example.json']

# The docs use inline Markdown links and reference definitions. Fenced examples
# are not links. Preserve labels, titles, fragments and external URLs on relocation.
INLINE_LINK = re.compile(r'(?P<prefix>!?\[[^\]\n]*\]\(\s*)(?P<target><[^>\n]+>|[^\s()]+)(?P<suffix>(?:[ \t]+(?:"[^"]*"|\'[^\']*\'))?\s*\))')
REFERENCE_LINK = re.compile(r'(?m)^(?P<prefix> {0,3}\[[^\]\n]+\]:[ \t]*)(?P<target><[^>\n]+>|[^\s]+)(?P<suffix>[^\n]*)$')
FENCED = re.compile(r'(?ms)(^ {0,3}`{3,}[^\n]*\n.*?^ {0,3}`{3,}[ \t]*(?:\n|$)|^ {0,3}~{3,}[^\n]*\n.*?^ {0,3}~{3,}[ \t]*(?:\n|$))')


def safe_member(name):
    if (not isinstance(name, str) or not name or '\\' in name
            or PurePosixPath(name).is_absolute() or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('Unsafe release path: ' + str(name))
    return name


def markdown_links(data, source, destination=None, names=None):
    """Validate local link destinations and optionally relocate this Markdown file."""
    def replace(match):
        target = match['target']
        bracketed = target.startswith('<')
        parts = urlsplit(target[1:-1] if bracketed else target)
        if parts.scheme == 'file' or re.match(r'^[A-Za-z]:[\\/]', target.strip('<>')):
            raise ValueError(f'{source}: local absolute link {target}')
        if parts.scheme or parts.netloc or not parts.path:
            return match[0]
        path = unquote(parts.path)
        if path.startswith('/') or '\\' in path:
            raise ValueError(f'{source}: unsafe local link {target}')
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
        safe_member(resolved)
        if names is not None and resolved not in names:
            raise ValueError(f'{source}: missing bundled link {target}')
        if destination is None:
            return match[0]
        relocated = posixpath.relpath(resolved, posixpath.dirname(destination) or '.')
        relocated = quote(relocated, safe='/@-._~')
        target = urlunsplit(('', '', relocated, parts.query, parts.fragment))
        if bracketed:
            target = '<' + target + '>'
        return match['prefix'] + target + match['suffix']

    chunks = FENCED.split(data.decode('utf-8'))
    for i in range(0, len(chunks), 2):
        chunks[i] = REFERENCE_LINK.sub(replace, INLINE_LINK.sub(replace, chunks[i]))
    return ''.join(chunks).encode('utf-8')


def package_content(commit):
    content = {}
    for name in FILES:
        safe_member(name)
        if name == 'MANIFEST.json':
            raise ValueError('Reserved release path: ' + name)
        if name in content:
            raise ValueError('Duplicate release path: ' + name)
        try:
            committed = subprocess.check_output(['git', 'show', f'{commit}:{name}'], cwd=ROOT, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            raise ValueError('Release source missing from commit: ' + name) from None
        if (ROOT / name).read_bytes() != committed:
            raise ValueError('Commit release changes before packaging: ' + name)
        content[name] = committed
    for source, destination in [('delivery/START-HERE.md', 'START-HERE.md'),
                                ('delivery/AGENT-RUNBOOK.md', '给Agent.md')]:
        if destination in content:
            raise ValueError('Generated release path already exists: ' + destination)
        content[destination] = markdown_links(content[source], source, destination)
    if '给使用者.txt' in content:
        raise ValueError('Generated release path already exists: 给使用者.txt')
    content['给使用者.txt'] = content['delivery/USER-GUIDE.txt']
    for name, data in content.items():
        if name.endswith('.md'):
            markdown_links(data, name, names=content)
    return content


def external_agent_handoff(archive_name):
    # This file lives beside the ZIP, so it deliberately contains no relative
    # Markdown links into a not-yet-extracted directory.
    return (f'# 给安装 Agent\n\n交付 ZIP：{archive_name}\n'
            f'校验文件：{archive_name}.sha256\n\n'
            '先核对 ZIP 的 SHA-256，再解压到固定目录。打开解压后的 wecom-auth-keeper 文件夹，'
            '先读根目录 AGENTS.md 和 给Agent.md，再按其中的安装与验收协议执行。'
            '不要直接从压缩包运行，也不要仅登记任务就报告成功。\n\n'
            '本文件是交付入口；具体支持范围、目标核验、首次接入、真实续期、自然定时、'
            '停用和故障处理均以包内文档为准。只维护用户指定且由当前登录主账号创建的 Bot，'
            '保留现有 CLI 绑定和其他业务服务。\n').encode('utf-8')


def build(output):
    output = Path(output).expanduser().absolute()
    if '\n' in output.name or '\r' in output.name:
        raise ValueError('Archive filename must be a single line')
    checksum_path = output.with_suffix(output.suffix + '.sha256')
    user_path, agent_path = output.parent / '给使用者.txt', output.parent / '给Agent.md'
    destinations = [output, checksum_path, user_path, agent_path]
    if len(set(destinations)) != len(destinations):
        raise ValueError('Release output paths must be distinct')
    for path in destinations:
        if path.exists() or path.is_symlink():
            raise FileExistsError('Refusing to overwrite release artifact: ' + str(path))
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    content = package_content(commit)
    manifest = {'format': 1, 'source_commit': commit, 'edition': 'macos-agent-installer',
                'support': {'macos': 'requires-device-acceptance', 'windows': 'no-automation-backend'},
                'files': {n: hashlib.sha256(data).hexdigest() for n, data in content.items()}}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        entries = {**content, 'MANIFEST.json': (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()}
        for name, data in sorted(entries.items()):
            item = zipfile.ZipInfo('wecom-auth-keeper/' + name, (2026, 11, 6, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            z.writestr(item, data)
    blob = archive.getvalue()
    checksum = hashlib.sha256(blob).hexdigest()
    artifacts = {user_path: content['给使用者.txt'], agent_path: external_agent_handoff(output.name),
                 checksum_path: (checksum + '  ' + output.name + '\n').encode(), output: blob}
    # Validate all source, aliases and links before publishing anything. Exclusive
    # creation also handles races; remove only files this call actually created.
    output.parent.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for path, data in artifacts.items():
            with path.open('xb') as stream:
                created.append(path)
                stream.write(data)
    except Exception:
        for path in reversed(created):
            path.unlink()
        raise
    return {'archive': str(output), 'sha256': checksum, 'source_commit': commit, 'files': len(content),
            'user_guide': str(user_path), 'agent_handoff': str(agent_path)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    print(json.dumps(build(p.parse_args().output)))
