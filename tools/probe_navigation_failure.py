#!/usr/bin/env python3
"""导航修复路径取证探针 v2（A 步收尾）。

v1 结论：粘贴落字 ✓、Return 被接收但**打开 640×560 全局搜索对话框**而非
导航（旧「Return 只导航」假设已被 WeCom 搜索行为漂移打破）。
v2 目标：不打 Return——枚举打字期下拉（320×702 形态，12:12:56 实证）中
的会话行，验名后点击，验证 heading 是否切换（桥侧 enumeration-gated 同款
路数）。全程取证，绝不点未验名行；不输入 authorizationList。
用法同 v1。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import keeper_ax as ax
import keeper_navigation as nav
from keeper_common import load_config
from renew import Renewal

OUT = Path("/tmp/keeper_nav_probe")


def log(step: str, **kv) -> None:
    line = json.dumps({"t": round(time.time(), 2), "step": step, **kv},
                      ensure_ascii=False, default=str)
    print(line, flush=True)
    with open(OUT / "events_v2.jsonl", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def window_inventory(engine) -> list:
    inv = []
    for w in engine.ax.ax_get(engine.app, "AXWindows") or []:
        inv.append({"frame": engine.ax.frame(w),
                    "subrole": engine.ax.ax_get(w, "AXSubrole"),
                    "title": (engine.text(w) or "")[:30]})
    return inv


def dropdown_row_texts(engine, window) -> list:
    """全部窗口内的静态文本行 (text, node, frame, root_frame)——v2 实测下拉
    为 218×73 AXSystemDialog（新形态），不再按角色白名单筛容器。"""
    rows = []
    roots = list(engine.ax.ax_get(engine.app, "AXWindows") or [])
    budget = [0]
    for root in roots:
        root_frame = engine.ax.frame(root)
        stack = [(root, 0)]
        while stack:
            node, depth = stack.pop()
            if depth > 16 or budget[0] > 1500:
                continue
            budget[0] += 1
            role = engine.ax.ax_get(node, "AXRole")
            if role == "AXStaticText":
                value = engine.ax.ax_get(node, "AXValue") or engine.ax.ax_get(node, "AXTitle")
                f = engine.ax.frame(node)
                if value and f and f[3] >= 18 and f[3] <= 40:
                    rows.append((str(value).strip(), node, f, root, root_frame))
            stack.extend((n, depth + 1) for n in engine.ax.ax_get(node, "AXChildren") or [])
    return rows


def cleanup_search(engine, native, window, search) -> None:
    """探针收场清场：清搜索框 + 点主窗聊天区压下拉（best-effort）。"""
    try:
        from ApplicationServices import AXUIElementSetAttributeValue
        AXUIElementSetAttributeValue(search, "AXValue", "")
    except Exception:
        pass
    try:
        f = engine.ax.frame(window)
        if f:
            from Quartz import (CGEventCreateMouseEvent, CGEventPost, CGPoint,
                                kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGHIDEventTap)
            cx, cy = f[0] + f[2] * 0.6, f[1] + f[3] * 0.55
            for kind in (kCGEventLeftMouseDown, kCGEventLeftMouseUp):
                CGEventPost(kCGHIDEventTap,
                            CGEventCreateMouseEvent(None, kind, CGPoint(cx, cy), 0))
                time.sleep(0.05)
    except Exception:
        pass


def main() -> int:
    cfg = load_config(sys.argv[1])
    engine = Renewal(cfg, ax)
    native, app = ax.application()
    engine.app = app
    log("start", frontmost=native.processIdentifier())

    windows = [(w, nav.global_search(engine, w))
               for w in engine.ax.ax_get(engine.app, "AXWindows") or []]
    windows = [(w, s) for w, s in windows if s is not None]
    if len(windows) != 1:
        log("verdict", result="navigation_unavailable", hits=len(windows))
        return 2
    window, search = windows[0]
    engine.ax.ax_perform(window, "AXRaise")
    time.sleep(0.3)

    if nav.heading_matches(engine, window, search):
        log("verdict", result="already_on_target_chat")
        return 0

    # 粘贴（v1 已证落字）——不打 Return
    engine.ax.replace_search(native, app, window, search, cfg["bot_chat_name"])
    log("pasted", axvalue=ax.ax_get(search, "AXValue"))

    deadline = time.monotonic() + 5
    target = []
    while time.monotonic() < deadline:
        rows = dropdown_row_texts(engine, window)
        target = [(t, n, r) for t, n, f, r, rf in rows if t == cfg["bot_chat_name"]]
        if target:
            break
        time.sleep(0.5)
    log("dropdown_rows",
        rows=[{"text": t[:30], "frame": f, "root_frame": rf}
              for t, _n, f, _r, rf in dropdown_row_texts(engine, window)[:25]],
        windows=window_inventory(engine))

    # 终局测量：打印全部含 bondie（不区分大小写/逗号形态）的行及其邻域
    all_rows = dropdown_row_texts(engine, window)
    hits = [(t, f, rf) for t, n, f, r, rf in all_rows if "bondie" in t.lower()]
    log("bondie_rows", rows=[{"text": t[:60], "frame": f, "root": rf} for t, f, rf in hits])
    target = [(t, n, r) for t, n, f, r, rf in all_rows
              if t == cfg["bot_chat_name"]
              and f and rf and rf[1] <= f[1] and f[1] + f[3] <= rf[1] + rf[3]
              and rf[0] <= f[0] and f[0] + f[2] <= rf[0] + rf[2]]
    log("in_bounds_exact_rows", count=len(target),
        frames=[ax.frame(n) for _t, n, _r in target])
    if not target:
        cleanup_search(engine, native, window, search)
        log("verdict", result="target_row_not_found", count=0)
        return 3
    # 消歧实验：精确命中按视觉序（y 升序）逐个尝试，heading 验证把关；
    # 记录每行的邻域文本（同 row 的兄弟静态文本）供消歧规则设计。
    for idx, (_t, node, row_root) in enumerate(sorted(target, key=lambda r: ax.frame(r[1])[1] if ax.frame(r[1]) else 0)):
        f = ax.frame(node)
        log("candidate", idx=idx, frame=f,
            siblings=[t for t, n2, f2, r2, rf2 in dropdown_row_texts(engine, window)
                      if f2 and abs(f2[1] - f[1]) < 26 and f2[0] >= f[0]][:6])
        try:
            engine.ax.click(node, row_root)
        except Exception as exc:
            log("click_failed", idx=idx, error=str(exc)[:120])
            continue
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if nav.heading_matches(engine, window, search):
                cleanup_search(engine, native, window, search)
                log("verdict", result="row_click_navigation_succeeded", idx=idx)
                return 0
            time.sleep(0.4)
        # heading 不匹配——打印真实 heading 文本（名字形态测量）
        field = engine.ax.frame(search)
        headings = [t for t, n2, f2, r2, rf2 in dropdown_row_texts(engine, window)
                    if f2 and field and f2[0] >= field[0] + field[2]
                    and abs(f2[1] - field[1]) < 60]
        log("candidate_failed_heading", idx=idx, heading_candidates=headings[:5],
            axvalue=ax.ax_get(search, "AXValue"))
    log("windows_after", inventory=window_inventory(engine))
    cleanup_search(engine, native, window, search)
    log("verdict", result="row_click_did_not_navigate", tried=len(target))
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
