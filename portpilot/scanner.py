"""扫描引擎：lsof 抓 TCP LISTEN 端口，ps/lsof 补进程信息，按规则分类。"""

import os
import re
import subprocess
from dataclasses import dataclass


@dataclass
class Listener:
    port: int
    pid: int
    name: str      # 进程名
    command: str   # 完整命令行
    cwd: str       # 工作目录（可能为空）
    category: str  # ai / other / protected
    uid: int

    @property
    def key(self):
        return (self.pid, self.port)

    def short(self, width=58) -> str:
        where = self.cwd.replace(os.path.expanduser("~"), "~") if self.cwd else ""
        label = f":{self.port}  {self.name}"
        if where:
            label += f"  ·  {where}"
        return label[: width - 1] + "…" if len(label) > width else label


def _run(cmd: list) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return r.stdout
    except Exception:
        return ""


def scan_listeners(config: dict) -> list:
    """返回当前所有 TCP LISTEN 的 Listener 列表（按端口排序）。"""
    out = _run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-F", "pcn"])
    raw = []
    pid = name = None
    for line in out.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("c"):
            name = line[1:]
        elif line.startswith("n") and pid is not None:
            m = re.search(r":(\d+)$", line[1:])
            if m:
                raw.append((pid, name or "?", int(m.group(1))))
    # 同一进程同端口多地址（IPv4/IPv6）去重
    seen = {}
    for p, n, port in raw:
        seen[(p, port)] = n

    pids = {p for p, _ in seen}
    psinfo = _ps_info(pids)
    cwdinfo = _cwd_info(pids)

    listeners = []
    for (p, port), n in seen.items():
        ppid, uid, command = psinfo.get(p, (0, -1, n))
        cwd = cwdinfo.get(p, "")
        cat = classify(p, port, command, cwd, uid, config)
        listeners.append(Listener(port, p, n, command, cwd, cat, uid))
    listeners.sort(key=lambda l: (l.category != "ai", l.port))
    return listeners


def _ps_info(pids: set) -> dict:
    """pid -> (ppid, uid, command)"""
    if not pids:
        return {}
    out = _run(["ps", "-o", "pid=,ppid=,uid=,command=", "-p", ",".join(map(str, pids))])
    info = {}
    for line in out.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) == 4:
            info[int(parts[0])] = (int(parts[1]), int(parts[2]), parts[3])
    return info


def _cwd_info(pids: set) -> dict:
    """pid -> cwd（仅限本用户进程可得）"""
    if not pids:
        return {}
    out = _run(["lsof", "-a", "-d", "cwd", "-Fn", "-p", ",".join(map(str, pids))])
    cwd = {}
    cur = None
    for line in out.splitlines():
        if line.startswith("p"):
            cur = int(line[1:])
        elif line.startswith("n") and cur is not None:
            cwd[cur] = line[1:]
            cur = None
    return cwd


def classify(pid: int, port: int, command: str, cwd: str, uid: int, config: dict) -> str:
    """三层分类：protected 兜底 → watch_dirs 命中 → ai_patterns 命中 → other。"""
    myuid = os.getuid()
    # 非本用户进程 / 内核进程 / ps 查不到的：一律受保护
    if uid != myuid or uid == -1 or pid in (0, 1, 2):
        return "protected"
    if port in config.get("protected_ports", []):
        return "protected"
    for pat in config.get("protected_patterns", []):
        if re.search(pat, command, re.I):
            return "protected"
    # 工作目录命中观察目录 → AI 服务
    for d in config.get("watch_dirs", []):
        d = os.path.realpath(os.path.expanduser(d))
        if cwd and (cwd == d or cwd.startswith(d + os.sep)):
            return "ai"
    # 命令特征命中 → AI 服务
    for pat in config.get("ai_patterns", []):
        if re.search(pat, command, re.I):
            return "ai"
    return "other"
