"""Opt-in native chat/history search. No messages, URLs opened outside WeCom, or permissions changed.

Search only chooses a candidate conversation. A link matching both configured
Bot identifiers, then the resulting page identity, is still required by Renewal.
"""
from keeper_common import KeeperError


def label(engine, node):
    # WeCom exposes several toolbar names only as AXHelp tooltips.
    return engine.text(node) or str(engine.ax.ax_get(node, "AXHelp") or "").strip()


def chrome(engine, root):
    """Exclude conversation rows, search-result text, web content and editors."""
    stack = [(root, 0)]
    total = 0
    while stack:
        node, depth = stack.pop()
        total += 1
        if total > 1000 or depth > 15:
            raise KeeperError("tree_incomplete", "Native navigation tree exceeds limits")
        role = engine.ax.ax_get(node, "AXRole")
        if role in {"AXScrollArea", "AXTable", "AXWebArea", "AXTextArea"}:
            continue
        yield node
        stack.extend((child, depth + 1) for child in engine.ax.ax_get(node, "AXChildren") or [])


def global_search(engine, window):
    outer = engine.ax.frame(window)
    if not outer:
        return None
    x, y, width, height = outer
    if width < 500 or height < 300:
        return None
    matches = []
    for node in chrome(engine, window):
        bounds = engine.ax.frame(node)
        if (engine.ax.ax_get(node, "AXRole") == "AXTextField" and bounds
                and engine.contains(outer, bounds)
                and 0 <= bounds[0] - x < min(width * .35, 200)
                and 0 <= bounds[1] - y < 90 and bounds[2] >= 80):
            matches.append(node)
    return matches[0] if len(matches) == 1 else None


def heading_matches(engine, window, search):
    field = engine.ax.frame(search)
    if not field:
        return False
    candidates = []
    for node in chrome(engine, window):
        bounds = engine.ax.frame(node)
        if (bounds and engine.ax.ax_get(node, "AXRole") in {"AXStaticText", "AXTextField"}
                and bounds[0] >= field[0] + field[2]
                and abs(bounds[1] - field[1]) < 60
                and engine.text(node) == engine.cfg["bot_chat_name"]):
            candidates.append(node)
    return len(candidates) == 1


def chat_row_candidates(engine):
    """打字期搜索下拉的会话行候选 (text, node, frame, root)。

    2026-11-17 实测（tools/probe_navigation_failure.py）：下拉为 app 级窗口
    （渲染完成形态 ~320×702 AXSystemDialog，渲染初期更小）；行 = 高
    18-40px 的 AXStaticText。主窗会话列表 below-fold 行报**虚拟坐标**
    （y 远超根窗口底），一律以「frame 完整落在其根窗口界内」过滤——
    界外行绝不可点。"""
    out = []
    budget = [0]
    for root in engine.ax.ax_get(engine.app, "AXWindows") or []:
        outer = engine.ax.frame(root)
        stack = [(root, 0)]
        while stack:
            node, depth = stack.pop()
            if depth > 16 or budget[0] > 1500:
                continue
            budget[0] += 1
            if engine.ax.ax_get(node, "AXRole") == "AXStaticText":
                text, bounds = engine.text(node), engine.ax.frame(node)
                if (text and bounds and 18 <= bounds[3] <= 40
                        and engine.contains(outer, bounds)):
                    out.append((text, node, bounds, root))
            stack.extend((child, depth + 1)
                         for child in engine.ax.ax_get(node, "AXChildren") or [])
    return out


def select_chat(engine, native, window, search):
    """从搜索下拉选择目标会话：唯一「精确同名且界内」行才点，否则如实失败。

    2026-11-17 修复（AZW 每小时残窗事故根因之一）：WeCom 搜索行为漂移后
    Return 打开的是全局搜索对话框而非导航（连续 83 小时
    navigation_target_not_found）。改为枚举+验名+点击——绝不 Return、
    绝不点未验名/界外/歧义行；点击后仍以 heading 验证收尾。"""
    expected = engine.cfg["bot_chat_name"]

    def exact_rows():
        return [row for row in chat_row_candidates(engine) if row[0] == expected]

    rows = engine.wait(exact_rows, lambda found: len(found) >= 1,
                       "navigation_target_not_found", timeout=5)
    if len(rows) != 1:
        raise KeeperError("navigation_target_not_found",
                          "Ambiguous conversation rows in the search dropdown")
    _, node, _bounds, root = rows[0]
    engine.ax.click(node, root)
    engine.wait(lambda: heading_matches(engine, window, search), bool,
                "navigation_target_not_found", timeout=8)


def restore_navigation(engine):
    """导航遗留面板的 best-effort 清理（2026-11-17 事故根治配套）。

    两步清场（零坐标盲点）：① 置空全局搜索框——打字期下拉随之收起
    （探针实测）；② 聊天记录面板开着时工具栏钮显示「关闭聊天记录」，
    唯一命中才点。逐步独立守卫，一步失败不吞其余；返回逐步结果，绝不抛。
    残余的搜索对话框类 CG 窗（如有）属 wecom-bridge 弹窗守卫的既定职责域
    （2026-11-17 起按窗 pacing ≤tick+60s 自动点除）——两层互补，不在本仓
    重复实现。"""
    steps = {}
    if engine.app is None:
        return steps  # 尚未 open 过——无导航遗留可清
    windows = list(engine.ax.ax_get(engine.app, "AXWindows") or [])
    for window in windows:
        search = global_search(engine, window)
        if search is not None:
            try:
                engine.ax.set_value(search, "")
                steps["search_cleared"] = True
            except Exception:
                steps["search_cleared"] = False
    for window in windows:
        closers = [node for node in chrome(engine, window)
                   if engine.ax.ax_get(node, "AXRole") == "AXButton"
                   and label(engine, node) == "关闭聊天记录"]
        if len(closers) == 1:
            try:
                engine.ax.click(closers[0], window)
                steps["history_panel_closed"] = True
            except Exception:
                steps["history_panel_closed"] = False
            break
    return steps


def open_chat_history(engine, native):
    windows = []
    for window in engine.ax.ax_get(engine.app, "AXWindows") or []:
        search = global_search(engine, window)
        if search is not None:
            windows.append((window, search))
    if len(windows) != 1:
        raise KeeperError("navigation_unavailable", "Expected one native WeCom chat search")
    window, search = windows[0]
    engine.focus_window(native, window, "navigation_unavailable")
    if not heading_matches(engine, window, search):
        engine.ax.replace_search(native, engine.app, window, search, engine.cfg["bot_chat_name"])
        # Search results are asynchronous; a row is only clicked after its
        # exact name is verified inside the dropdown's own window bounds. It
        # cannot send a message, and the resulting title AND the configured
        # link identity are checked before continuing.
        select_chat(engine, native, window, search)

    def history_fields():
        if not heading_matches(engine, window, search):
            raise KeeperError("navigation_target_changed", "Conversation changed during navigation")
        field = engine.ax.frame(search)
        return [node for node in chrome(engine, window)
                if engine.ax.ax_get(node, "AXRole") == "AXTextField"
                and engine.ax.frame(node)
                and engine.ax.frame(node)[0] > field[0] + field[2]
                and engine.ax.frame(node)[1] > field[1] + 40]

    buttons = [node for node in chrome(engine, window)
               if engine.ax.ax_get(node, "AXRole") == "AXButton"
               and label(engine, node) in {"查找聊天记录", "关闭聊天记录"}]
    if len(buttons) != 1:
        raise KeeperError("navigation_unavailable", "Expected one chat history control")
    if label(engine, buttons[0]) == "查找聊天记录":
        engine.ax.click(buttons[0], window)
    fields = engine.wait(history_fields, lambda nodes: len(nodes) == 1,
                         "navigation_unavailable", timeout=5)
    engine.ax.replace_search(native, engine.app, window, fields[0], "authorizationList")

    def verified_links():
        if not heading_matches(engine, window, search):
            raise KeeperError("navigation_target_changed", "Conversation changed during navigation")
        return engine.visible_links([window])

    engine.wait(verified_links, bool, "link_not_visible", timeout=12)
