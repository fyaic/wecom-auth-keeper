"""Narrowly calibrated close control for the native 5.0.13 permission sheet."""


def embedded_close_button(engine, native, window, page):
    ax = engine.ax
    parent, sheet = page, None
    for _ in range(16):
        parent = ax.ax_get(parent, 'AXParent')
        if parent is None or ax.ax_get(parent, 'AXRole') == 'AXWindow':
            break
        if ax.ax_get(parent, 'AXRole') == 'AXSheet':
            sheet = parent
            break
    if sheet is None or ax.client_version(native) != '5.0.13':
        return None
    # This adapter is for the observed Chinese native sheet only. The blank
    # button has no accessible name; require its complete header arrangement,
    # sheet ancestry and page-relative geometry, never screen coordinates.
    bounds = ax.frame(page)
    if (not bounds or bounds != ax.frame(sheet)
            or not engine.contains(ax.frame(window), bounds)
            or sum(ax.ax_get(n, 'AXRole') == 'AXWebArea' for n in engine.walk(sheet)) != 1):
        return None
    x, y, width, height = bounds
    if width < 400 or height < 300:
        return None
    headings, buttons = [], []
    for node in engine.walk(page):
        frame = ax.frame(node)
        if not frame or not engine.contains(bounds, frame):
            continue
        nx, ny, nw, nh = frame
        role = ax.ax_get(node, 'AXRole')
        if (role == 'AXStaticText' and engine.text(node) == '可使用权限'
                and abs(nx - x - 48) <= 2 and abs(ny - y - 29) <= 2
                and 60 <= nw <= 160 and 14 <= nh <= 24):
            headings.append(node)
        if role == 'AXButton' and ny < y + 70:
            buttons.append(node)
    if len(headings) != 1 or len(buttons) != 1:
        return None
    button = buttons[0]
    bx, by, bw, bh = ax.frame(button)
    if (abs(bx + bw - x - width + 48) > 2 or abs(by - y - 24) > 2
            or abs(bw - 28) > 2 or abs(bh - 28) > 2
            or ax.ax_get(button, 'AXSubrole') == 'AXCloseButton'
            or 'AXPress' not in ax.action_names(button)):
        return None
    for attribute in ('AXTitle', 'AXValue', 'AXDescription', 'AXHelp', 'AXIdentifier', 'AXDOMIdentifier'):
        if str(ax.ax_get(button, attribute) or '').strip():
            return None
    return button
