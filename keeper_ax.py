"""Small native AX adapter. No bridge imports, configuration or network access."""
import time
from AppKit import NSWorkspace
from ApplicationServices import (
    AXIsProcessTrusted, AXUIElementCopyAttributeValue, AXUIElementCreateApplication,
    AXUIElementPerformAction, AXUIElementCopyActionNames, AXValueGetValue, kAXValueCGPointType, kAXValueCGSizeType,
)
from Quartz import (
    CGEventCreateMouseEvent, CGEventPost, CGPoint, kCGEventLeftMouseDown,
    kCGEventLeftMouseUp, kCGHIDEventTap,
)


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
        raise RuntimeError("Accessibility permission unavailable")
    apps = [a for a in NSWorkspace.sharedWorkspace().runningApplications() if a.bundleIdentifier() == "com.tencent.WeWorkMac"]
    apps = [a for a in apps if ax_get(AXUIElementCreateApplication(a.processIdentifier()), "AXWindows")]
    if len(apps) != 1:
        raise RuntimeError("Expected one running WeCom application")
    return apps[0], AXUIElementCreateApplication(apps[0].processIdentifier())


def activate(app):
    app.activateWithOptions_(1 << 1)
