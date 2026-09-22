"""Shared configuration, durable local state and process locking (no GUI imports)."""
import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from urllib.parse import urlsplit

DEFAULT_ROWS = ["新建与编辑文档", "搜索与获取文档内容"]


class KeeperError(Exception):
    def __init__(self, code, message, exit_code=2):
        super().__init__(message)
        self.code, self.exit_code = code, exit_code


def load_config(path, *, probes=False):
    path = Path(path).expanduser().resolve()
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KeeperError("invalid_config", "Cannot read configuration JSON", 3) from exc
    if not isinstance(cfg, dict):
        raise KeeperError("invalid_config", "Configuration must be an object", 3)
    keys = ("read_docid", "write_docid", "write_sheet") if probes else ("bot_chat_name", "aibotid", "str_aibotid")
    for key in keys:
        value = cfg.get(key)
        if not isinstance(value, str) or not value.strip() or value.strip().startswith("<"):
            raise KeeperError("invalid_config", f"Missing configuration field: {key}", 3)
    rows = cfg.setdefault("target_rows", DEFAULT_ROWS.copy())
    if not isinstance(rows, list) or not rows or any(not isinstance(r, str) or not r.strip() for r in rows) or len(set(rows)) != len(rows):
        raise KeeperError("invalid_config", "target_rows must contain unique nonempty names", 3)
    for key in ("bridge_send_link", "bridge_monitor"):
        if key in cfg and not isinstance(cfg[key], bool):
            raise KeeperError("invalid_config", f"{key} must be boolean", 3)
    for key, default in (("probe_timeout", 90), ("renew_timeout", 240), ("lock_wait", 10)):
        value = cfg.setdefault(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 600:
            raise KeeperError("invalid_config", f"{key} must be between 0 and 600 seconds", 3)
    for key in ("bridge_url", "notify_to", "wecom_cli", "venv_python"):
        if key in cfg and not isinstance(cfg[key], str):
            raise KeeperError("invalid_config", f"{key} must be a string", 3)
    if (cfg.get("bridge_send_link") or cfg.get("bridge_monitor")) and not cfg.get("bridge_url"):
        raise KeeperError("invalid_config", "bridge_url is required for enabled bridge features", 3)
    for key in ("wecom_cli", "venv_python"):
        value = cfg.get(key, "")
        if value and "/" in value:
            dest = Path(value).expanduser()
            cfg[key] = str(dest if dest.is_absolute() else path.parent / dest)
    if cfg.get("bridge_url"):
        parsed = urlsplit(cfg["bridge_url"])
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise KeeperError("invalid_config", "bridge_url must be an HTTP(S) service URL without credentials/query", 3)
    for key, default in (("state_file", "~/.wecom-auth-renew/state.json"), ("log_file", "~/.wecom-auth-renew/renew.log")):
        raw = cfg.setdefault(key, default)
        if not isinstance(raw, str) or not raw.strip():
            raise KeeperError("invalid_config", f"{key} must be a nonempty path", 3)
        dest = Path(raw).expanduser()
        cfg[key] = str(dest if dest.is_absolute() else path.parent / dest)
    destinations = [Path(cfg[key]).resolve() for key in ("state_file", "log_file")]
    if len(set(destinations)) != 2 or path in destinations:
        raise KeeperError("invalid_config", "Config, state and log must use distinct paths", 3)
    cfg["_config_path"] = str(path)
    return cfg


def executable(value, default):
    value = os.path.expanduser(value or default)
    result = shutil.which(value)
    if not result:
        raise KeeperError("missing_executable", f"Executable not available: {default}", 3)
    return result


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


@contextlib.contextmanager
def process_lock(path, wait=10):
    """flock follows process lifetime. Never unlink a lock inode in use."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise KeeperError("lock_busy", "Another operation holds the lock", 4)
                time.sleep(min(0.1, max(0, deadline - time.monotonic())))
        yield
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def gui_lock_path():
    # All bots sharing a desktop must use the same lock, irrespective of config.
    return Path.home() / ".wecom-auth-renew" / "desktop.lock"


def emit_error(exc):
    if isinstance(exc, KeeperError):
        return {"ok": False, "error": exc.code, "message": str(exc)}, exc.exit_code
    # Raw API/GUI errors can contain private URLs or document contents.
    return {"ok": False, "error": "unexpected_error", "message": type(exc).__name__}, 2
