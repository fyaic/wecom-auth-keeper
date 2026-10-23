"""Small native AX adapter. No bridge imports, configuration or network access."""
import time
from contextlib import contextmanager
from keeper_common import KeeperError
from AppKit import NSWorkspace, NSPasteboard, NSPasteboardItem, NSPasteboardTypeString
from ApplicationServices import (
    AXIsProcessTrusted, AXUIElementCopyAttributeValue, AXUIElementCreateApplication,
    AXUIElementPerformAction, AXUIElementCopyActionNames, AXValueGetValue, kAXValueCGPointType, kAXValueCGSizeType,
)
from Quartz import (
    CGEventCreateMouseEvent, CGEventPost, CGPoint, kCGEventLeftMouseDown,
    kCGEventLeftMouseUp, kCGHIDEventTap,
    CGEventCreateKeyboardEvent, CGEventSetFlags, CGEventPostToPid, kCGEventFlagMaskCommand,
)


def require_search_focus(native, app, window, element):
    """Keyboard input is limited to a verified native search field, never a composer."""
    front = NSWorkspace.sharedWorkspace().frontmostApplication()
    if (front is None or front.processIdentifier() != native.processIdentifier()
            or ax_get(app, "AXFocusedWindow") != window
            or ax_get(app, "AXFocusedUIElement") != element
            or ax_get(element, "AXRole") != "AXTextField"):
        raise KeeperError("navigation_focus_lost", "Search focus changed; navigation stopped")


def search_key(native, app, window, element, code, flags=0):
    require_search_focus(native, app, window, element)
    for down in (True, False):
        event = CGEventCreateKeyboardEvent(None, code, down)
        CGEventSetFlags(event, flags)
        CGEventPostToPid(native.processIdentifier(), event)
        time.sleep(0.05)


@contextmanager
def temporary_clipboard(text):
    """Preserve all pasteboard formats; do not overwrite a concurrent user's copy."""
    board = NSPasteboard.generalPasteboard()
    saved = []
    for source in board.pasteboardItems() or []:
        item = NSPasteboardItem.alloc().init()
        for kind in source.types():
            data = source.dataForType_(kind)
            if data is not None:
                item.setData_forType_(data, kind)
        saved.append(item)
    board.clearContents()
    board.setString_forType_(text, NSPasteboardTypeString)
    own_change = board.changeCount()
    try:
        yield
    finally:
        if board.changeCount() == own_change:
            board.clearContents()
            if saved:
                board.writeObjects_(saved)


def replace_search(native, app, window, element, text):
    click(element, window)
    time.sleep(0.15)
    require_search_focus(native, app, window, element)
    with temporary_clipboard(text):
        search_key(native, app, window, element, 0, kCGEventFlagMaskCommand)  # Command-A
        search_key(native, app, window, element, 9, kCGEventFlagMaskCommand)  # Command-V
        deadline = time.monotonic() + 3
        while ax_get(element, "AXValue") != text:
            require_search_focus(native, app, window, element)
            if time.monotonic() >= deadline:
                raise KeeperError("navigation_input_failed", "Search text was not accepted")
            time.sleep(0.05)


def submit_search(native, app, window, element, expected):
    if ax_get(element, "AXValue") != expected:
        raise KeeperError("navigation_input_failed", "Search text changed before selection")
    search_key(native, app, window, element, 36)  # Return; only while search has focus


def ax_get(element, attribute):
    error, value = AXUIElementCopyAttributeValue(element, attribute, None)
    return value if error == 0 else None


def ax_perform(element, action):
    return AXUIElementPerformAction(element, action)


def frame(element):
    position, size = ax_get(element, "AXPosition"), ax_get(element, "AXSize")
    if position is None or size is None:
        return None
    try:
        ok1, point = AXValueGetValue(position, kAXValueCGPointType, None)
        ok2, extent = AXValueGetValue(size, kAXValueCGSizeType, None)
        if ok1 and ok2:
            return float(point.x), float(point.y), float(extent.width), float(extent.height)
    except (TypeError, ValueError):
        pass
    return None


def click(element, window):
    bounds, outer = frame(element), frame(window)
    if not bounds or not outer:
        raise RuntimeError("Element geometry unavailable")
    error, actions = AXUIElementCopyActionNames(element, None)
    actions = actions if error == 0 else []
    if "AXScrollToVisible" in actions:
        ax_perform(element, "AXScrollToVisible")
        # WebKit updates geometry asynchronously after scrolling.
        for _ in range(20):
            bounds = frame(element)
            if bounds and outer[1] <= bounds[1] and bounds[1] + bounds[3] <= outer[1] + outer[3]:
                break
            time.sleep(0.05)
    if not bounds:
        raise RuntimeError("Element geometry unavailable after scrolling")
    x, y, w, h = bounds
    wx, wy, ww, wh = outer
    cx, cy = x + w / 2, y + h / 2
    if w <= 0 or h <= 0 or not (wx <= cx <= wx + ww and wy <= cy <= wy + wh):
        raise RuntimeError("Element outside target window; scroll it into view first")
    if "AXPress" in actions and ax_perform(element, "AXPress") == 0:
        return
    for kind in (kCGEventLeftMouseDown, kCGEventLeftMouseUp):
        CGEventPost(kCGHIDEventTap, CGEventCreateMouseEvent(None, kind, CGPoint(cx, cy), 0))
        time.sleep(0.05)


def application():
    if not AXIsProcessTrusted():
        # Check in this exact process, without prompting or attempting to grant
        # access. A terminal's permission is not proof about a launchd child.
        raise KeeperError("accessibility_permission_unavailable", "Accessibility access is unavailable to this process", 3)
    apps = [a for a in NSWorkspace.sharedWorkspace().runningApplications() if a.bundleIdentifier() == "com.tencent.WeWorkMac"]
    if not apps:
        raise KeeperError("wecom_not_running", "No running WeCom application was found", 3)
    apps = [a for a in apps if ax_get(AXUIElementCreateApplication(a.processIdentifier()), "AXWindows")]
    if not apps:
        raise KeeperError("wecom_window_unavailable", "No WeCom window is accessible in this session")
    if len(apps) > 1:
        raise KeeperError("wecom_multiple_instances", "Multiple windowed WeCom instances are accessible")
    return apps[0], AXUIElementCreateApplication(apps[0].processIdentifier())


def activate(app):
    app.activateWithOptions_(1 << 1)
