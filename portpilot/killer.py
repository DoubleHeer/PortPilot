"""停止引擎：SIGTERM 优雅停止 → 超时 SIGKILL 兜底，处理整个进程树，全部写审计。"""

import os
import signal
import subprocess
import time

from . import store


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def descendants(pid: int) -> list:
    """递归收集所有子进程（如 uvicorn 的 reloader 子进程、npm 的 node 树）。"""
    out = subprocess.run(
        ["pgrep", "-P", str(pid)], capture_output=True, text=True
    ).stdout.split()
    result = []
    for p in out:
        p = int(p)
        result.append(p)
        result.extend(descendants(p))
    return result


def stop(pid: int, port: int = 0, name: str = "", force: bool = False,
         timeout: float = 3.0, audit: bool = True) -> tuple:
    """停止进程及其子进程树。返回 (ok: bool, detail: str)。"""
    if pid == os.getpid():
        return False, "拒绝停止自身"
    if pid in (0, 1, 2):
        return False, f"拒绝停止系统核心进程 pid={pid}（如 launchd）"
    if not _alive(pid):
        if audit:
            store.record_action("stop", pid, port, name, "进程已不存在")
        return True, "进程已不存在"

    victims = descendants(pid) + [pid]
    detail_parts = []

    if not force:
        # 先子后父发 SIGTERM，父进程最后收到信号可正常清理
        for v in reversed(victims):
            try:
                os.kill(v, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not any(_alive(v) for v in victims):
                break
            time.sleep(0.2)

    remain = [v for v in victims if _alive(v)]
    if remain:
        for v in remain:
            try:
                os.kill(v, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        time.sleep(0.3)

    still = [v for v in victims if _alive(v)]
    if still:
        ok, detail = False, f"SIGKILL 后仍存活: {still}"
    else:
        ok = True
        sig = "SIGKILL" if remain else ("SIGTERM" if not force else "SIGKILL(直接)")
        detail = f"已停止 {len(victims)} 个进程 ({sig}): {victims}"

    if audit:
        store.record_action("stop" if ok else "stop-failed", pid, port, name, detail)
    return ok, detail
