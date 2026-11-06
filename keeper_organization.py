"""Verified organization rows; calibrated 5.0.13 sidebar entry, never avatar/chat hints."""
from keeper_common import KeeperError
from keeper_navigation import global_search


def walk(ax, root):
    stack = [(root, 0)]
    count = 0
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > 1500 or depth > 20:
            raise KeeperError('tree_incomplete', 'Organization menu exceeds bounds')
        yield node
        stack.extend((c, depth + 1) for c in ax.ax_get(node, 'AXChildren') or [])


def menu_rows(engine):
    """Only rows in native corp menus, not matching names in chats or web pages."""
    ax = engine.ax
    result = []
    for window in ax.ax_get(engine.app, 'AXWindows') or []:
        f = ax.frame(window)
        if not f or not 150 <= f[2] <= 400:
            continue
        for row in walk(ax, window):
            if ax.ax_get(row, 'AXRole') != 'AXRow':
                continue
            nodes = list(walk(ax, row))
            icons = {str(ax.ax_get(n, 'AXDescription') or '') for n in nodes
                     if ax.ax_get(n, 'AXRole') == 'AXImage'}
            if not icons & {'icon corp list selected', 'icon corp list unselected'}:
                continue
            names = [engine.text(n) for n in nodes if ax.ax_get(n, 'AXRole') == 'AXStaticText']
            if len(names) == 1:
                result.append((names[0], 'icon corp checkmark' in icons, row, window))
    return result


def ensure_organization(engine, native):
    name = engine.cfg.get('organization_selector_name')
    if not name:
        raise KeeperError('organization_profile_required', 'Configure exact menu name and validated sidebar profile')
    if engine.cfg.get('organization_navigation') != 'sidebar-5.0.13' or engine.ax.client_version(native) != '5.0.13':
        raise KeeperError('organization_version_unsupported', 'Organization adapter requires verified WeCom 5.0.13')
    ax = engine.ax
    windows = [w for w in ax.ax_get(engine.app, 'AXWindows') or [] if global_search(engine, w) is not None]
    if len(windows) != 1:
        raise KeeperError('org_switcher_not_found', 'Expected one native chat window')
    main = windows[0]
    engine.focus_window(native, main, 'org_switcher_not_found')

    def entry():
        current = [w for w in ax.ax_get(engine.app, 'AXWindows') or [] if global_search(engine, w) is not None]
        if len(current) != 1:
            raise KeeperError('org_switcher_not_found', 'Main window changed ambiguously')
        ax.open_organization_menu(native, engine.app, current[0])

    def close_menu():
        current = [w for w in ax.ax_get(engine.app, 'AXWindows') or [] if global_search(engine, w) is not None]
        if len(current) != 1:
            raise KeeperError('org_switcher_not_found', 'Cannot safely dismiss organization menu')
        ax.click(global_search(engine, current[0]), current[0])
        engine.wait(lambda: menu_rows(engine), lambda r: not r, 'organization_menu_close_timeout', timeout=5)

    def open_menu():
        rows = menu_rows(engine)
        if not rows:
            # 5.0.13 exposes the bottom org icon with invalid AX bounds. Only
            # this version-gated entry click uses calibrated window-relative geometry.
            entry()
            rows = engine.wait(lambda: menu_rows(engine), bool, 'org_switcher_not_found', timeout=4)
        return rows

    rows = open_menu()
    matches = [r for r in rows if r[0] == name]
    if len(matches) != 1 or sum(r[1] for r in rows) != 1:
        # Close only the menu we opened; no guessed row or substring selection.
        close_menu()
        raise KeeperError('organization_not_listed', 'Exact unique organization row / selected marker unavailable')
    previous = next(r[0] for r in rows if r[1])
    if previous == name:
        close_menu()
        return {'switched': False, 'organization': name}
    ax.click(matches[0][2], matches[0][3])
    engine.wait(lambda: menu_rows(engine), lambda r: not r, 'organization_switch_timeout', timeout=5)
    engine.sleep(1)
    rows = open_menu()
    selected = [r[0] for r in rows if r[1]]
    close_menu()
    if selected != [name]:
        raise KeeperError('organization_switch_timeout', 'Selected organization did not match target')
    return {'switched': previous != name, 'organization': name}
