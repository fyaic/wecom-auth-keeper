#!/usr/bin/env python3
"""One-shot compatibility probe for OTHER devices: WeCom version + AX structure snapshot.

企业微信更新后页面逻辑可能变化导致续期失效；本脚本在受影响的设备上运行（只读、不点击、
不发送），把版本号、窗口结构、组织标记、聊天搜索框、可见链接、授权页 WebArea 全部
打印成 JSON。把输出发回维护者即可远程适配，无需在目标设备上调试。
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import keeper_ax  # noqa: E402


def text(ax, node):
    for key in ("AXTitle", "AXDescription", "AXValue", "AXStringValue"):
        value = ax.ax_get(node, key)
        if value and isinstance(value, str) and value.strip():
            return value
    return ""


def walk(ax, node, depth=0):
    yield node, depth
    for child in (ax.ax_get(node, "AXChildren") or []):
        yield from walk(ax, child, depth + 1)


def wecom_version():
    for path in ("/Applications/企业微信.app/Contents/Info.plist",):
        try:
            out = subprocess.run(["defaults", "read", path, "CFBundleShortVersionString"],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
            build = subprocess.run(["defaults", "read", path, "CFBundleVersion"],
                                   capture_output=True, text=True, timeout=5).stdout.strip()
            return f"{out} ({build})"
        except Exception:
            continue
    return "unknown"


def main():
    report = {"wecom_version": wecom_version(), "platform": sys.platform,
              "trusted_for_ax": False, "windows": []}
    try:
        native, app = keeper_ax.application()
        report["trusted_for_ax"] = True
        for window in (keeper_ax.ax_get(app, "AXWindows") or []):
            frame = keeper_ax.frame(window) or (0, 0, 0, 0)
            if frame[2] < 300:
                continue
            info = {"title": str(keeper_ax.ax_get(window, "AXTitle") or ""),
                    "frame": [int(v) for v in frame],
                    "webarea_urls": [], "link_texts": [], "text_fields": [],
                    "buttons": [], "org_or_chat_texts": []}
            count = 0
            for node, _depth in walk(keeper_ax, window):
                count += 1
                role = keeper_ax.ax_get(node, "AXRole")
                t = text(keeper_ax, node)
                if role == "AXWebArea":
                    url = str(keeper_ax.ax_get(node, "AXURL") or "")
                    if url:
                        info["webarea_urls"].append(url[:160])
                elif role == "AXLink" and t:
                    info["link_texts"].append(t[:80])
                elif role == "AXTextField" and t:
                    info["text_fields"].append(t[:40])
                elif role == "AXButton" and t:
                    info["buttons"].append(t[:24])
                if t and any(k in t for k in ("组织", "机器人", "授权", "聊天记录", "bot")):
                    info["org_or_chat_texts"].append(t[:60])
                if count > 4000:
                    break
            info["buttons"] = info["buttons"][:20]
            info["org_or_chat_texts"] = info["org_or_chat_texts"][:20]
            info["link_texts"] = info["link_texts"][:10]
            info["webarea_urls"] = info["webarea_urls"][:5]
            report["windows"].append(info)
    except Exception as exc:  # noqa: BLE001
        report["ax_error"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
