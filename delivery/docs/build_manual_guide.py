#!/usr/bin/env python3
"""Build the 2026-11-11 manual screenshot guide without interacting with WeCom."""
from pathlib import Path
from hashlib import sha256
import json
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from pypdf import PdfReader

from pdf_options import options, register_fonts

ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/'docs/assets/manual-renewal'
OUT, font_options=options(ROOT, __doc__)
NAME='纯人工手动续期-企业微信Bot图文指南.pdf'
register_fonts('CN', 'CNB', font_options)
W,H=A4
M=44
CW=W-2*M
INK=HexColor('#182C36'); MUTED=HexColor('#546875'); TEAL=HexColor('#137C78')
LIGHT=HexColor('#EFF7F5'); RULE=HexColor('#D9E4E5'); ORANGE=HexColor('#C65A28')
c=canvas.Canvas(str(OUT/NAME),pagesize=A4,pageCompression=1,invariant=1)
c.setTitle('企业微信 Bot | 纯人工手动续期图文指南')
c.setAuthor('WeCom Auth Keeper')
c.setSubject('企业微信 5.0.13 Mac 中文版真实 UI；手动取消与重新授权，核对到期时间')

def p(text,top,x=M,width=CW,size=10.8,leading=18,color=INK,bold=False):
    st=ParagraphStyle('p',fontName='CNB' if bold else 'CN',fontSize=size,leading=leading,
                      textColor=color,wordWrap='CJK',splitLongWords=False)
    q=Paragraph(text,st); _,h=q.wrap(width,H)
    assert top+h<H-48,(text[:30],top+h)
    q.drawOn(c,x,H-top-h)
    return top+h

def header(page,title,subtitle):
    c.setFillColor(TEAL); c.rect(M,H-42,24,3,fill=1,stroke=0)
    p('AUTH KEEPER / 手动操作指南',31,M+35,300,8.4,12,MUTED)
    c.setFillColor(MUTED); c.setFont('CN',8)
    c.drawRightString(W-M,H-41,'真实界面 · 无需代码')
    p(title,68,size=23,leading=32,bold=True)
    p(subtitle,110,size=10.5,leading=17,color=MUTED)
    c.setStrokeColor(RULE); c.setLineWidth(.6); c.line(M,43,W-M,43)
    c.setFont('CN',8); c.drawString(M,27,'企业微信 5.0.13 Mac 中文版 | 2026.11.11')
    c.drawRightString(W-M,27,f'{page} / 5')

def box(text,top,x=M,width=CW,pad=13):
    st=ParagraphStyle('b',fontName='CN',fontSize=10.4,leading=17,textColor=INK,wordWrap='CJK')
    q=Paragraph(text,st); _,h=q.wrap(width-pad*2,H); total=h+pad*2
    assert top+total<H-48
    c.setFillColor(LIGHT); c.roundRect(x,H-top-total,width,total,6,fill=1,stroke=0)
    q.drawOn(c,x+pad,H-top-pad-h)
    return top+total

def picture(name,top,x=M,width=CW,crop=None,highlights=()):
    # PDF viewport clipping only. The original screenshot pixels remain unchanged.
    path=ASSETS/name
    with Image.open(path) as im: iw,ih=im.size
    if crop is None: crop=(0,0,iw,ih)
    sx,sy,sw,sh=crop; scale=width/sw; height=sh*scale
    assert top+height<H-48,(name,top+height)
    c.saveState()
    clip=c.beginPath(); clip.rect(x,H-top-height,width,height); c.clipPath(clip,stroke=0)
    c.drawImage(str(path),x-sx*scale,H-top-(ih-sy)*scale,width=iw*scale,height=ih*scale)
    c.restoreState()
    c.setStrokeColor(RULE); c.setLineWidth(.7); c.rect(x,H-top-height,width,height,fill=0,stroke=1)
    for rx,ry,rw,rh in highlights:
        c.setStrokeColor(ORANGE); c.setLineWidth(1.5)
        c.roundRect(x+(rx-sx)*scale,H-top-(ry-sy+rh)*scale,rw*scale,rh*scale,3,fill=0,stroke=1)
    return top+height

def caption(text,top): return p(text,top,size=9,leading=14,color=MUTED)

header(1,'企业微信 Bot 手动续期','适用于已经接入业务、需要恢复或延长使用权限的 Bot。全程在企业微信中点击。')
y=box('<b>开始前只确认三件事</b><br/>登录的是 Bot 创建者主账号；当前组织正确；要处理的是业务正在使用的那个 Bot。截图中的名称仅作示例，请找你自己的 Bot。',154)
y=p('01  找到 Bot，再打开资料卡',y+21,size=14,leading=22,bold=True)
left=M; right=314
y0=y+14
p('<b>先核对组织</b><br/>在企业微信左下角的企业切换入口，查看当前组织；需要时切到 Bot 所属组织。同名 Bot 可能属于不同组织。',y0,left,238)
p('<b>已有私聊</b><br/>搜索 Bot 名称，打开与它的私聊，再点击聊天顶部的 Bot 名称。资料卡中点击“去管理”。',y0+107,left,238)
p('<b>还没有私聊</b><br/>从“机器人”目录找它；找不到入口时，可查“更多 → 通讯录 → 智能机器人”。从资料卡的“发消息”进入私聊，无需先发一条消息。',y0+214,left,238)
picture('02-bot-card.jpg',y0,right,237,highlights=[(43,467,555,98)])
caption('图 1  Bot 资料卡：“去管理”进入管理页面。',y0+286)
y=box('进入“管理机器人”列表后，找到<b>同一个 Bot</b>，再点它右侧的“详情”。列表可能分“企业创建 / 成员创建”；不要因为列表里没有它就新建 Bot。',y0+337)
caption('本图文使用 Mac 5.0.13（95049）实拍。其他版本及 Windows 的入口可能不同；没有对应按钮时，请按实际界面核对，不套用固定位置。',y+16)
c.showPage()

header(2,'02  进入“可使用权限”','在“机器人详情”核对名称，再进入权限列表。这里不需要查看或修改 API 配置。')
y=p('点击下图橙框标出的“可使用权限”。它与“API 配置”是两个不同入口。',155)
y=picture('03-bot-details.jpg',y+14,highlights=[(405,185,590,68),(235,940,1560,92)])
y=caption('图 2  机器人详情。需要时向下滚动，找到“可使用权限”。',y+8)
y=p('进入权限页后，先看你要处理的那一行：',y+21,bold=True)
y=p('<b>显示“已授权”及有效期：</b>记录旧到期时间；要提前续期，按第 3 页先取消，再立即授权。',y+8)
y=p('<b>显示蓝色“授权”按钮：</b>如果这是业务原来使用的权限，按第 4 页直接授权。仅凭此按钮不能判断它是“已过期”还是“从未授权”。',y+8)
box('只处理需要的权限。多个权限应一项一项完成：取消一项、重授这一项、核对日期，再处理下一项。',y+16)
c.showPage()

header(3,'03  未到期时：先取消授权','已有有效授权但需要提前续期时使用。取消后会短暂失去这项能力，应立即接着重新授权。')
y=p('<b>1.</b> 点击目标权限右侧的“已授权”或旁边下拉箭头，再点红色“取消授权”。',154)
y=picture('05a-revoke-menu.jpg',y+14,crop=(90,245,1250,200),highlights=[(1138,284,178,52),(1095,339,215,80)])
y=caption('图 3  已授权下拉菜单（局部放大）。操作的是这一行，不是整个 Bot。',y+8)
y=p('<b>2.</b> 确认弹窗提示后，点击蓝色“取消授权”。如果 Bot 或权限选错，点“暂不操作”返回。',y+22)
y=picture('05b-revoke-confirm.jpg',y+14,x=M+47,width=CW-94,crop=(380,455,680,365),highlights=[(727,687,272,75)])
y=caption('图 4  取消授权的最终确认框。只有点击这里的蓝色按钮才会执行取消。',y+8)
box('<b>下一步不要停：</b>返回同一行，看到蓝色“授权”后，立即按第 4 页重新授权。不要一次取消全部权限，也不要取消后直接关页。',y+19)
c.showPage()

header(4,'04  重新授权，核对新日期','已经过期且显示“授权”时，也从这一步开始；不必再寻找取消入口。')
y=p('<b>1.</b> 点击目标权限那一行的蓝色“授权”。如出现确认页，核对 Bot 和权限范围后确认；如果提示只有创建者可操作，请交由创建者主账号处理。',154)
y=picture('06-grant-button.jpg',y+13,crop=(80,140,1270,290),highlights=[(1118,295,193,76)])
y=caption('图 5  “授权”按钮状态示例，来自示例 Bot 的真实权限页。',y+8)
y=p('<b>2.</b> 等待该行显示绿色“已授权”和“有效期至”。提前续期时，新到期时间必须晚于你记录的旧时间。',y+21)
y=picture('04-permission-expiry.jpg',y+13,crop=(80,140,1270,290),highlights=[(1060,290,260,90)])
y=caption('图 6  核对状态与日期的位置。图中日期是取图时的原状态，不代表本次续期结果。',y+8)
y=p('<b>3.</b> 关闭权限页，再从同一个 Bot 重新打开一次，确认新到期时间仍然保留。只看见“已授权”，不能证明有效期已经延长。',y+20)
box('如果取消后重授失败，先恢复当前这一项，再处理其他权限。不要重建 Bot、重置 Secret 或重新扫码来解决权限过期。',y+16)
c.showPage()

header(5,'05  多权限逐项核对，最后关页','文档、微盘和邮箱的读写能力可能分成多行；续了“发送消息”不代表它们也续了。')
y=picture('07-document-permissions.jpg',151,crop=(90,140,1255,435),highlights=[(121,235,1200,307)])
y=caption('图 7  文档的写入与读取分开授权。按钮显示“授权”也可能是从未授予，按业务需要确认。',y+8)
y=p('按实际用途找对应行',y+17,size=12,leading=20,bold=True)
rows=[
    ('消息','发送消息'),
    ('文档 / 表格','搜索与获取文档内容；需要写入时另处理“新建与编辑文档”'),
    ('微盘','搜索与获取微盘文件内容；需要写入时另处理“上传与更新微盘文件”'),
    ('邮箱','搜索与获取邮件内容；需要发信时另处理“发送邮件”'),
]
for label,desc in rows:
    y+=7
    p(label,y,M,95,10.2,17,TEAL,True)
    end=p(desc,y,M+103,CW-103,10.2,17)
    c.setStrokeColor(RULE); c.setLineWidth(.5); c.line(M,H-end-6,W-M,H-end-6)
    y=end+8
y=p('完成后做三件事',y+15,size=12,leading=20,bold=True)
y=p('核对所有所需权限的新到期时间；用日常业务做一次轻量验证；点击权限页右上角“×”关闭页面，避免影响其他使用企业微信界面的服务。',y+6,size=10.3,leading=17)
y=p('手动方式不会替你定时续期。按页面实际到期时间设一个提前一天的提醒；下次重复同样步骤。',y+7,size=10.3,leading=17)
y=p('<b>常见卡点：</b>找不到 Bot 先核对组织和目录；提示创建者限制先核对账号；日期没延长则重开页面复查；仍报过期时检查是否漏了另一项读写权限。',y+10,size=9.7,leading=16,color=MUTED)
caption('取图说明：截图展示入口、菜单与状态；本次未点击最终取消或授权按钮，未改变业务权限。截图中的姓名、Bot 名称及日期均为示例，实际操作以自己的页面为准。',y+12)
c.save()

reader=PdfReader(str(OUT/NAME)); assert len(reader.pages)==5
text='\n'.join(page.extract_text() or '' for page in reader.pages)
for term in ['创建者主账号','可使用权限','取消授权','暂不操作','有效期至','提前一天','原状态','新建与编辑文档']:
    assert term in ''.join(text.split()),term
assert '\ufffd' not in text
print(json.dumps({'pdf': str(OUT/NAME), 'pages': 5,
                  'sha256': sha256((OUT/NAME).read_bytes()).hexdigest(),
                  'text_checks_passed': True}, ensure_ascii=False))
