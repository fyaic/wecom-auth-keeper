#!/usr/bin/env python3
"""Build the 2026-11-11 business-user PDF; never modifies the archived release."""
from pathlib import Path
from xml.sax.saxutils import escape
import hashlib
import json

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.pagesizes import A4
from pypdf import PdfReader

from pdf_options import options, register_fonts

ROOT = Path(__file__).resolve().parents[2]
OUT, font_options = options(ROOT, __doc__)
PDF_NAME = '给使用者-企业微信Bot自动续期.pdf'
register_fonts('CN', 'CN-Bold', font_options)

W, H = A4
M = 44
CW = W - M * 2
INK = HexColor('#182C36')
MUTED = HexColor('#546875')
TEAL = HexColor('#137C78')
LIGHT = HexColor('#EFF7F5')
RULE = HexColor('#D9E4E5')
FONT = 10.8
LEADING = 17.5
pdf = OUT / PDF_NAME
c = canvas.Canvas(str(pdf), pagesize=A4, pageCompression=1, invariant=1)
c.setTitle('企业微信 Bot 自动续期 | 使用说明')
c.setAuthor('WeCom Auth Keeper')
c.setSubject('Mac 使用者安装、验收与日常维护说明；配套已验收版本 2fd6762')

def para(text, x, top, width, size=FONT, leading=LEADING, color=INK, bold=False):
    style = ParagraphStyle('p', fontName='CN-Bold' if bold else 'CN', fontSize=size,
                           leading=leading, textColor=color, wordWrap='CJK',
                           alignment=TA_LEFT, splitLongWords=False)
    p = Paragraph(text, style)
    _, h = p.wrap(width, H)
    if top + h > H - 50:
        raise ValueError(f'Content exceeds page: {text[:45]}, bottom={top+h}')
    p.drawOn(c, x, H-top-h)
    return top + h

def rule(top):
    c.setStrokeColor(RULE)
    c.setLineWidth(.6)
    c.line(M, H-top, W-M, H-top)

def header(page, label):
    c.setFillColor(TEAL)
    c.rect(M, H-41, 24, 3, fill=1, stroke=0)
    para('AUTH KEEPER  /  MAC', M+35, 31, 220, 8.5, 12, MUTED)
    c.setFont('CN', 8.5)
    c.setFillColor(MUTED)
    c.drawRightString(W-M, H-41, label)
    rule(H-43)
    c.setFont('CN', 8)
    c.drawString(M, 27, '使用说明  2026.11.11  |  配套版本 2fd6762')
    c.drawRightString(W-M, 27, f'{page} / 2')

def heading(n, title, top):
    c.setFillColor(TEAL)
    c.roundRect(M, H-top-20, 24, 20, 4, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('CN-Bold', 10)
    c.drawCentredString(M+12, H-top-14, n)
    para(title, M+34, top-1, CW-34, 13, 22, INK, True)
    return top + 32

def box(text, top, size=10.4, leading=17, pad=14):
    style = ParagraphStyle('box', fontName='CN', fontSize=size, leading=leading,
                           textColor=INK, wordWrap='CJK', splitLongWords=False)
    p=Paragraph(text, style)
    _, ph=p.wrap(CW-pad*2, H)
    height=ph+pad*2
    if top + height > H-50:
        raise ValueError(f'Box exceeds page: {top + height}')
    c.setFillColor(LIGHT)
    c.roundRect(M,H-top-height,CW,height,7,fill=1,stroke=0)
    p.drawOn(c,M+pad,H-top-pad-ph)
    return top+height

source_guide = (ROOT / 'delivery/USER-GUIDE.txt').read_text()
prompt = next(p.strip() for p in source_guide.split('\n\n') if p.startswith('请按 AGENTS.md'))

header(1, '开始安装')
y=para('企业微信 Bot 自动续期',M,67,CW,25,34,INK,True)
y=para('使用说明 · 把安装包交给你的 AI Agent',M,y+6,CW,12,20,MUTED)
y=para('在权限过期前自动续期，完成后关闭权限页。安装通过后，由电脑上的系统脚本定时运行，不需要 AI 常驻。',M,y+15,CW)

y=box('<b>先确认：这台电脑能维护这个 Bot</b><br/>使用 Mac，并在企业微信中登录 Bot 创建者主账号，维护自己创建的 Bot。告诉 Agent 你要维护的组织、Bot 名称和权限；不要默认选择其他业务 Bot。',y+18)

y=heading('01','三步开始',y+22)
steps=[
    ('解压并保留', '把配套 ZIP 解压到长期保留的位置，安装后不要移动或删除。'),
    ('交给 Agent', '用 WorkBuddy、Codex 或 Kimi Code 打开解压后的整个文件夹；Agent 需要能操作本机文件、终端和企业微信。'),
    ('复制下面的指令', '可补充你的组织、Bot 名称，以及消息、文档、微盘或邮箱等所需权限；只启用逐项实测通过的权限。'),
]
for i,(title,body) in enumerate(steps,1):
    y=para(f'<b>{i}. {title}</b>　{body}',M,y,CW)
    y+=8

y=para('复制给 Agent',M,y+5,CW,10.5,17,TEAL,True)
y=box(escape(prompt),y+7,size=10.5,leading=17.7)
y=para('首次安装需联网，可能需要你确认一次系统权限或首次业务权限。无需向分发者发送密码、Secret、个人配置或聊天记录。',M,y+12,CW,9.5,15,MUTED)
c.showPage()

header(2, '验收与日常使用')
y=para('实测完成，才算安装成功',M,67,CW,23,32,INK,True)
y=para('Agent 应在这台设备上跑完下面三项，并留下可核对的结果。',M,y+9,CW,11,18,MUTED)

y=heading('02','安装后，核对结果卡',y+22)
checks=[
    ('目标正确', '组织、Bot、权限与需求一致；续期入口位于本机账号与目标 Bot 的私聊中。'),
    ('续期真实发生', '由脚本完成续期，记录续期前后的到期时间；结束后自动关闭权限页。'),
    ('定时确实触发', '经过一次自然定时触发验证，再启用登录后自动加载的每小时任务，在到期前 24 小时续期。'),
]
for title,body in checks:
    y=para(f'<b>{title}</b>　{body}',M,y,CW)
    y+=10
y=box('结果卡还应写明：项目和日志位置、停止与恢复方法。仅显示“已创建定时任务”或“权限目前有效”，不能证明自动续期成功。',y+1,10.4,17)

y=heading('03','平时怎么用',y+24)
y=para('电脑保持开机，桌面可操作，企业微信保持登录。睡眠、锁屏、退出登录都可能影响续期；更换电脑、账号或升级企业微信后，让 Agent 重新验收。',M,y,CW)
y+=14
y=para('<b>出现问题</b>　把原文件夹交给 Agent，并说：',M,y,CW)
y=para('“检查现有任务和最近结果，保留 Bot 绑定与恢复记录，定位失败后复测。” 不要自行重新创建 Bot 或删除配置。',M,y+5,CW,10.4,17)
y+=14
y=para('<b>不再使用</b>　让 Agent 执行：',M,y,CW)
y=para('“持久停用这个 Bot 的续期任务，下次登录也不再自动启动；保留配置和恢复记录。” 无需退出企业微信或停掉其他服务。',M,y+5,CW,10.4,17)

y+=21
rule(y)
y=para('适用范围与实测边界',M,y+14,CW,10,17,MUTED,True)
y=para('已实测：macOS 26.4.1（Apple Silicon）、企业微信 5.0.13 中文版；远端 Kimi Code 完成安装演练、“发送消息”真实续期及自然定时验证。WorkBuddy 本轮未实机验证。',M,y+6,CW,9.4,15,MUTED)
y=para('每台新设备都须验收后启用。其他企业微信版本、语言及其他权限需适配或逐项验证；Windows 暂不支持。',M,y+6,CW,9.4,15,MUTED)
c.save()

# Confirm copyable Chinese text and complete, unclipped page bounds.
reader=PdfReader(str(pdf))
assert len(reader.pages)==2
extracted='\n'.join(p.extract_text() or '' for p in reader.pages)
compact=''.join(extracted.split())
assert ''.join(prompt.split()) in compact, 'Copyable Agent prompt differs from source'
for term in ['AGENTS.md','delivery/AGENT-RUNBOOK.md','Windows 暂不支持','持久停用','自然定时','主账号','24 小时']:
    assert ''.join(term.split()) in compact, term
assert '\ufffd' not in extracted
print(json.dumps({'pdf': str(pdf), 'pages': 2,
                  'sha256': hashlib.sha256(pdf.read_bytes()).hexdigest(),
                  'text_checks_passed': True}, ensure_ascii=False))
