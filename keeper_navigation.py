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
        # Search results are asynchronous and not AX-readable on WeCom 5.0.12.
        # Return only navigates. It cannot send a message, and the resulting
        # title AND the configured link identity are checked before continuing.
        engine.sleep(1.5)
        engine.ax.submit_search(native, engine.app, window, search, engine.cfg["bot_chat_name"])
        engine.wait(lambda: heading_matches(engine, window, search), bool,
                    "navigation_target_not_found", timeout=8)

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
