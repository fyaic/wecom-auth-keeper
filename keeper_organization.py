"""Ensure the desktop WeCom sits on the target organization before navigation.

多组织账号下，桌面企微停留在别的组织时聊天导航必然失败（navigation_target_not_found）。
本模块在导航前检查主窗口是否可见目标组织标记；不可见则点头像 → 组织面板 → 点目标组织行。
只做组织切换，不改任何权限；面板不存在目标组织时报错而非乱点。
"""
import keeper_ax
from keeper_common import KeeperError

ORG_ROW_HINTS = ("有限公司", "组织")  # 面板行的兜底特征（仅日志用）


def _text(ax, node):
    for key in ("AXTitle", "AXDescription", "AXValue", "AXStringValue"):
        value = ax.ax_get(node, key)
        if value and isinstance(value, str) and value.strip():
            return value
    return ""


def _walk(ax, node, depth=0):
    yield node, depth
    for child in (ax.ax_get(node, "AXChildren") or []):
        yield from _walk(ax, child, depth + 1)


def _main_window(ax, app):
    best = None
    for window in ax.ax_get(app, "AXWindows") or []:
        frame = ax.frame(window)
        if frame and frame[2] >= 500 and (best is None or frame[2] > ax.frame(best)[2]):
            best = window
    if best is None:
        raise KeeperError("window_unavailable", "No main WeCom window", 3)
    return best


def _markers(cfg):
    name = cfg.get("organization_name") or ""
    hints = [name] + list(cfg.get("organization_markers") or ())
    return [h for h in hints if h]


def org_visible(ax, app, cfg):
    """Target-org content currently visible in the main window (chat list shows its chats)."""
    window = _main_window(ax, app)
    markers = _markers(cfg)
    if not markers:
        return True  # 未配置组织名：不做检查（单组织账号无需此步）
    for node, _depth in _walk(ax, window):
        for marker in markers:
            if marker and marker in _text(ax, node):
                return True
    return False


def ensure_organization(engine, native):
    """Switch to cfg['organization_name'] if its content is not visible. Idempotent."""
    ax, app = engine.ax, engine.ax.application()[1]
    if org_visible(ax, app, engine.cfg):
        return {"switched": False}
    name = engine.cfg.get("organization_name")
    if not name:
        return {"switched": False}  # 未配置不检查
    window = _main_window(ax, app)
    frame = ax.frame(window)
    # 头像按钮：主窗口左上角区域的 Button（实测 62x38）
    avatar = None
    for node, _depth in _walk(ax, window):
        if ax.ax_get(node, "AXRole") != "AXButton":
            continue
        f = ax.frame(node)
        if (f and frame[0] - 5 <= f[0] <= frame[0] + 90
                and frame[1] - 5 <= f[1] <= frame[1] + 70
                and 30 <= f[2] <= 90 and 25 <= f[3] <= 60):
            avatar = node
            break
    if avatar is None:
        raise KeeperError("org_switcher_not_found", "Avatar/org button not found in main window", 3)
    ax.click(avatar, window)
    engine.sleep(2)
    # 面板内找目标组织行
    row = None
    for node, _depth in _walk(ax, window):
        if name in _text(ax, node):
            row = node
            break
    if row is None:
        raise KeeperError("organization_not_listed",
                          f"Target organization row not found in switcher panel: {name}", 3)
    ax.click(row, window)
    # 等组织内容出现（切换有加载过程）
    engine.wait(lambda: org_visible(ax, engine.ax.application()[1], engine.cfg), bool,
                "organization_switch_timeout", timeout=25)
    return {"switched": True, "organization": name}
