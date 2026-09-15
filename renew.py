#!/usr/bin/env python3
"""wecom-auth-renew —— 企业微信 wecom-cli 能力授权自动续期（通用独立版 v1.0）

解决的问题：wecom-cli 的「文档」能力授权（读/写两条独立线）各 7 天到期，到期报
850003、不会因调用自动续期、官方无自动续期机制（#87 挂起待产品评估）。本方案在
到期后自动完成续期：打开授权页 → 点击到期行的「授权」→ 新 7 天时钟。

通道（2026-09 经两周实机验证）：把 authorizationList 续期链接作为消息发进/存在于
机器人聊天 → 点击气泡内 AXLink（聊天区 AX 全稳定）→ 企微内置浏览器新窗口打开
「可使用权限」页（登录会话现成，零扫码）→ 页面为规整 AXWebArea，能力名/已授权/
有效期至/授权按钮全可读 → 点击到期行的「授权」AXButton。

用法：
  renew.py --config <config.json> --check    只读：两条权限线状态与有效期
  renew.py --config <config.json> --renew    续期：对到期行点击授权（轮询确认+补点）

依赖：①macOS 企微桌面端已登录（会话属于能授权该 bot 的成员）②bridge pyobjc 环境
（venv_python 指向，仅用其 AX 库）③可选 bridge HTTP（bridge_send_link=true 时用于
把链接发进聊天；false 则点击聊天中已有链接——链接为静态地址、历史消息里永久可点）
配置：复制 config.example.json → config.json（已 gitignore），填 bot 身份三要素。

实战记录：2026-09-14 读线 16:12 / 写线 20:04 两次真实续期成功（写线全程无人值守，
检测→续期→复探→通知闭环）。完整踩坑实录见 docs/auth-model.md。
"""
import json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timedelta

CONFIG_PATH = None
CFG = None
_no_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))
RENEW_LOCK = "/tmp/wecom-auth-renew.lock"


def load_config():
    global CONFIG_PATH, CFG
    for i, a in enumerate(sys.argv):
        if a == "--config" and i + 1 < len(sys.argv):
            CONFIG_PATH = sys.argv[i + 1]
    if not CONFIG_PATH or not os.path.exists(CONFIG_PATH):
        print(json.dumps({"ok": False, "error": f"config not found: {CONFIG_PATH}"}))
        sys.exit(3)
    CFG = json.load(open(CONFIG_PATH))
    for k in ("bot_chat_name", "aibotid", "str_aibotid"):
        if not CFG.get(k) or str(CFG[k]).startswith("<"):
            print(json.dumps({"ok": False, "error": f"config field {k} unset"}))
            sys.exit(3)


def _p(key):
    return os.path.expanduser(CFG.get(key, ""))


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    lp = _p("log_file")
    if lp:
        os.makedirs(os.path.dirname(lp), exist_ok=True)
        with open(lp, "a") as f:
            f.write(line + "\n")


load_config()
# bridge 的 pydantic Settings 从 cwd 找 .env——必须在 import 其模块前落位（launchd 无 cwd）
BRIDGE_SRC = CFG.get("wecom_bridge_src", "")
if BRIDGE_SRC and os.path.isdir(BRIDGE_SRC):
    os.chdir(os.path.dirname(BRIDGE_SRC.rstrip("/")))
    sys.path.insert(0, BRIDGE_SRC)
from wecom.ax.helpers import create_app_ref, ax_get, ax_perform, click_at  # noqa: E402
from AppKit import NSWorkspace  # noqa: E402

RENEW_URL = (f"https://work.weixin.qq.com/ai/aiHelper/authorizationList?from=chat"
             f"&forceInnerBrowser=1&aibotid={CFG['aibotid']}"
             f"&str_aibotid={CFG['str_aibotid']}&type=1")
TARGET_ROWS = CFG.get("target_rows", ["新建与编辑文档", "搜索与获取文档内容"])

ZW = re.compile(r"[\u200b\u200c\u200d\ufeff\ufffc]")
_app = None


def clean(s):
    """去零宽/对象替换符——企微 AX 文本常带 \u200b，精确匹配前必清"""
    return ZW.sub("", str(s or "")).strip()


def http_json(method, path, body=None, timeout=15):
    req = urllib.request.Request(CFG["bridge_url"] + path, method=method,
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with _no_proxy.open(req, timeout=timeout) as r:
        return json.loads(r.read())


def frame(el):
    try:
        ps, ss = str(ax_get(el, "AXPosition")), str(ax_get(el, "AXSize"))
        m1 = re.search(r"x:([\d.]+) y:([\d.]+)", ps)
        m2 = re.search(r"w:([\d.]+) h:([\d.]+)", ss)
        if not m1 or not m2:
            return None
        return float(m1.group(1)), float(m1.group(2)), float(m2.group(1)), float(m2.group(2))
    except Exception:
        return None


def wecom_pid():
    out = subprocess.run(["pgrep", "-x", "企业微信"], capture_output=True, text=True)
    return int(out.stdout.split()[0]) if out.stdout.strip() else None


def activate(pid):
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if a.processIdentifier == pid:
            a.activateWithOptions_(1 << 1)
            return


def find_all(pred, depth_max=24, cap=12):
    out = []

    def walk(el, depth):
        if len(out) >= cap or depth > depth_max:
            return
        if pred(el):
            out.append(el)
            return
        for k in (ax_get(el, "AXChildren") or []):
            walk(k, depth + 1)

    for w in (ax_get(_app, "AXWindows") or []):
        walk(w, 0)
    return out


def window_has_perm(win):
    flag = [False]

    def walk(el, depth=0):
        if flag[0] or depth > 10:
            return
        if "可使用权限" in str(ax_get(el, "AXTitle") or "") + str(ax_get(el, "AXValue") or ""):
            flag[0] = True
            return
        for k in (ax_get(el, "AXChildren") or []):
            walk(k, depth + 1)

    walk(win)
    return flag[0]


def send_link_message():
    """bridge 可用时把续期链接发进机器人聊天（保证最新链接在可视区底部）"""
    if not CFG.get("bridge_send_link"):
        return
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    r = http_json("POST", "/wecom/send",
                  {"to": CFG["bot_chat_name"],
                   "message": f"续期通道（自动，请忽略）{RENEW_URL}",
                   "idempotency_key": f"wlr-renew-{ts}"}, timeout=120)
    if not r.get("success"):
        log(f"bridge send failed: {r}")


def open_auth_window(pid, retries=2):
    """点击聊天中的授权链接 → 返回「可使用权限」窗口（重试整轮）"""
    for attempt in range(retries):
        send_link_message()
        activate(pid)
        time.sleep(1.0)
        links = find_all(lambda e: str(ax_get(e, "AXRole")) == "AXLink"
                         and "authorizationList" in str(ax_get(e, "AXValue") or "")
                         + str(ax_get(e, "AXTitle") or ""))
        if links:
            with_frame = [l for l in links if frame(l)]
            if with_frame:
                newest = max(with_frame, key=lambda e: frame(e)[1])
                x, y, w, h = frame(newest)
                click_at(x + w / 2, y + h / 2)
            else:
                rc = ax_perform(links[-1], "AXPress")
                log(f"link frame missing → AXPress rc={rc}")
                time.sleep(1.0)
            for _ in range(20):
                time.sleep(1.0)
                for win in (ax_get(_app, "AXWindows") or []):
                    if window_has_perm(win):
                        time.sleep(0.8)
                        return win
        log(f"auth window not opened (attempt {attempt + 1})")
        time.sleep(2.0)
    raise RuntimeError("授权页窗口未能打开（重试耗尽）")


def close_auth_window(win):
    try:
        cb = ax_get(win, "AXCloseButton")
        if cb is not None:
            ax_perform(cb, "AXPress")
            time.sleep(1.0)
    except Exception as e:
        log(f"close window err: {e}")


def parse_expiry(text):
    m = re.search(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})", text)
    if not m:
        return None
    mo, d, hh, mm = map(int, m.groups())
    now = datetime.now()
    dt = datetime(now.year, mo, d, hh, mm)
    if dt < now - timedelta(days=180):
        dt = dt.replace(year=dt.year + 1)
    return dt


def read_rows(win):
    """返回 {行名: {status: authorized|expired|missing, expiry: dt|None, btn: el|None}}
    关联规则（相对坐标，抗窗口位移）：状态列元素在行名右侧 Δx>350 且 Δy∈(0,70)"""
    target_clean = [clean(n) for n in TARGET_ROWS]
    texts = []

    def walk(el, depth):
        if depth > 12 or len(texts) > 200:
            return
        role = str(ax_get(el, "AXRole"))
        t = clean(ax_get(el, "AXTitle")) or clean(ax_get(el, "AXValue"))
        if role == "AXStaticText" and t:
            texts.append((t, el))
        elif role == "AXButton" and t == "授权":
            texts.append((t, el))
        for k in (ax_get(el, "AXChildren") or []):
            walk(k, depth + 1)

    walk(win, 0)
    anchors, expiries, btns = [], [], []
    for t, el in texts:
        f = frame(el)
        if f is None:
            continue
        x, y = f[0], f[1]
        if t in target_clean:
            anchors.append((x, y, t))
        elif t.startswith("有效期至"):
            expiries.append((x, y, parse_expiry(t)))
        elif t == "授权":
            btns.append((x, y, el))
    rows = {}
    for name in TARGET_ROWS:
        cname = clean(name)
        cand = [a for a in anchors if a[2] == cname]
        if not cand:
            rows[name] = {"status": "missing", "expiry": None, "btn": None}
            continue
        ax_, ay = min((a[0], a[1]) for a in cand)
        expiry = None
        btn = None
        for x, ey, dt in expiries:
            if x - ax_ > 350 and 0 < ey - ay < 70:
                expiry = dt if dt else expiry
        for x, by, el in btns:
            if x - ax_ > 350 and 0 < by - ay < 70:
                btn = el
        rows[name] = {"status": "expired" if btn else "authorized",
                      "expiry": expiry, "btn": btn}
    return rows


def click_renew(win, name, row, max_tries=3):
    """点授权并轮询确认（≤30s/轮），未中补点重试——首击偶发未中的闭环加固"""
    for try_i in range(max_tries):
        r = row["btn"] if try_i == 0 else None
        if r is None:
            r = read_rows(win).get(name, {}).get("btn")
            if r is None:
                return  # 行已 authorized——成功
        f = frame(r)
        if f is None:
            return
        click_at(f[0] + f[2] / 2, f[1] + f[3] / 2)
        time.sleep(1.5)
        for _ in range(3):  # 确认弹窗（变体词全收）
            confirms = find_all(lambda e: str(ax_get(e, "AXRole")) == "AXButton"
                                and any(k in str(ax_get(e, "AXTitle") or "")
                                        for k in ("确认", "确定", "重新授权", "同意")))
            if not confirms:
                break
            cf = frame(confirms[0])
            if cf is None:
                break
            click_at(cf[0] + cf[2] / 2, cf[1] + cf[3] / 2)
            time.sleep(1.2)
        t0 = time.time()
        while time.time() - t0 < 30:
            if read_rows(win).get(name, {}).get("status") == "authorized":
                return
            time.sleep(3.0)


def acquire_renew_lock(max_wait_s=150):
    import shutil
    waited = 0
    while waited < max_wait_s:
        if os.path.isdir(RENEW_LOCK):
            try:
                if time.time() - os.path.getmtime(RENEW_LOCK) > 300:
                    shutil.rmtree(RENEW_LOCK, ignore_errors=True)
                    continue
            except OSError:
                pass
            time.sleep(5)
            waited += 5
            continue
        try:
            os.mkdir(RENEW_LOCK)
            return RENEW_LOCK
        except FileExistsError:
            time.sleep(2)
            waited += 2
    return None


def release_renew_lock(lockdir):
    import shutil
    if lockdir:
        shutil.rmtree(lockdir, ignore_errors=True)


def set_monitor(mode):
    if not CFG.get("bridge_send_link"):
        return
    try:
        http_json("POST", "/wecom/monitor/mode", {"mode": mode})
    except Exception as e:
        log(f"monitor {mode} failed: {e}")


def main():
    global _app
    mode = "--renew" if "--renew" in sys.argv else "--check"
    pid = wecom_pid()
    if pid is None:
        print(json.dumps({"ok": False, "error": "WeCom not running"}))
        return 3
    lockdir = acquire_renew_lock()
    if lockdir is None:
        print(json.dumps({"ok": False, "error": "renew lock busy"}))
        return 4
    _app = create_app_ref(pid)
    try:
        set_monitor("observe")  # GUI 期间防消息监控抢界面（finally 恢复）
        win = open_auth_window(pid)
        rows_before = {}
        for _ in range(15):  # 权限行晚于页头渲染——轮询等行
            rows_before = read_rows(win)
            if any(r["status"] != "missing" for r in rows_before.values()):
                break
            time.sleep(1.0)
        result = {"mode": mode, "rows": {}}
        for name, row in rows_before.items():
            entry = {"status": row["status"],
                     "expiry": row["expiry"].strftime("%Y-%m-%d %H:%M") if row["expiry"] else None}
            if mode == "--renew" and row["status"] == "expired" and row["btn"] is not None:
                click_renew(win, name, row)
                na = read_rows(win).get(name, {})
                entry["renewed"] = na.get("status") == "authorized"
                entry["expiry_after"] = (na["expiry"].strftime("%Y-%m-%d %H:%M")
                                         if na.get("expiry") else None)
            result["rows"][name] = entry
        close_auth_window(win)
        sp = _p("state_file")
        if sp:
            os.makedirs(os.path.dirname(sp), exist_ok=True)
            json.dump({"read_at": datetime.now().isoformat(),
                       "expiries": {n: (r["expiry"].isoformat() if r.get("expiry") else None)
                                    for n, r in rows_before.items()}}, open(sp, "w"))
        result["ok"] = True
        print(json.dumps(result, ensure_ascii=False))
        log(f"mode={mode} " + json.dumps(result["rows"], ensure_ascii=False))
        return 0
    except Exception as e:
        log(f"ERROR {e}")
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 2
    finally:
        set_monitor("active")
        release_renew_lock(lockdir)


if __name__ == "__main__":
    sys.exit(main())
