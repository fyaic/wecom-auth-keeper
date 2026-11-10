import json
import keeper_ax as ax
from keeper_common import load_config
cfg = load_config("config-kaopu.json")
r = ax
native, app = r.application()
def walk(node, depth=0):
    yield node, depth
    for child in r.ax_get(node, "AXChildren") or []:
        yield from walk(child, depth + 1)
out = []
for win in r.ax_get(app, "AXWindows") or []:
    title = r.ax_get(win, "AXTitle")
    urls = set()
    for node, d in walk(win):
        role = r.ax_get(node, "AXRole")
        if role == "AXWebArea":
            u = r.ax_get(node, "AXURL") or r.ax_get(node, "AXValue")
            if u: urls.add(str(u)[:120])
    out.append({"title": str(title)[:60], "urls": list(urls)[:3]})
print(json.dumps(out, ensure_ascii=False, indent=1))
