"""CLI 入口：python3 -m portpilot [app|scan|history|actions|kill|kill-port]"""

import argparse
import sys
import time

from . import killer, scanner, store
from .config import load_config

TAG = {"ai": "AI", "other": "其他", "protected": "系统"}


def cmd_scan(args):
    cfg = load_config()
    listeners = scanner.scan_listeners(cfg)
    if not args.all:
        listeners = [l for l in listeners if l.category != "protected"] or listeners
    print(f"{'端口':<7}{'PID':<8}{'分类':<6}{'进程':<22}命令行")
    print("-" * 100)
    for l in listeners:
        print(f":{l.port:<6}{l.pid:<8}{TAG[l.category]:<6}{l.name[:20]:<22}{l.command[:60]}")
        if l.cwd:
            print(f"{'':<21}└─ cwd: {l.cwd}")
    n = {c: sum(1 for l in listeners if l.category == c) for c in TAG}
    print(f"\n共 {len(listeners)} 个监听：AI {n['ai']} / 其他 {n['other']} / 系统 {n['protected']}")


def cmd_history(args):
    rows = store.recent_events(args.n)
    for ts, ev, port, pid, name, cat, cmd in rows:
        t = time.strftime("%m-%d %H:%M:%S", time.localtime(ts))
        mark = "↑起" if ev == "up" else "↓停"
        print(f"{t}  {mark}  :{port}  {name}  [{TAG.get(cat, cat)}]  {cmd[:60]}")


def cmd_actions(args):
    rows = store.recent_actions(args.n)
    for ts, action, pid, port, name, detail in rows:
        t = time.strftime("%m-%d %H:%M:%S", time.localtime(ts))
        print(f"{t}  [{action}]  pid={pid} :{port}  {name}\n    {detail}")


def _find_by_port(cfg, port):
    for l in scanner.scan_listeners(cfg):
        if l.port == port:
            return l
    return None


def cmd_kill(args):
    cfg = load_config()
    listeners = scanner.scan_listeners(cfg)
    targets = []
    port = getattr(args, "port", None)
    pid = getattr(args, "pid", None)
    if port is not None:
        targets = [l for l in listeners if l.port == port]
        if not targets:
            print(f"端口 {port} 上没有监听进程")
            sys.exit(1)
    else:
        targets = [l for l in listeners if l.pid == args.pid]
        if not targets:
            # 进程可能存在但未监听端口，仍允许直接停（视为非保护）
            t = type("L", (), {"pid": args.pid, "port": 0, "name": "?", "category": "other"})
            targets = [t]
    for t in targets:
        if t.category == "protected" and not args.force:
            print(f"拒绝停止受保护进程 pid={t.pid} :{getattr(t, 'port', '?')}（--force 跳过保护）")
            sys.exit(1)
    failed = False
    for t in targets:
        ok, detail = killer.stop(t.pid, getattr(t, "port", 0), getattr(t, "name", "?"),
                                 force=getattr(args, "force", False))
        print(("OK " if ok else "FAIL ") + detail)
        failed = failed or not ok
    if failed:
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(prog="portpilot", description="本机端口哨兵")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("app", help="启动菜单栏应用（默认）")

    sp = sub.add_parser("scan", help="扫描当前监听端口")
    sp.add_argument("--all", action="store_true", help="包含系统服务")

    sp = sub.add_parser("history", help="端口出现/消失历史")
    sp.add_argument("n", nargs="?", type=int, default=30)

    sp = sub.add_parser("actions", help="停止操作审计")
    sp.add_argument("n", nargs="?", type=int, default=20)

    sp = sub.add_parser("kill", help="停止进程（PID）")
    sp.add_argument("pid", type=int)
    sp.add_argument("--force", action="store_true", help="跳过保护直接 SIGKILL")

    sp = sub.add_parser("kill-port", help="停止监听某端口的进程")
    sp.add_argument("port", type=int)
    sp.add_argument("--force", action="store_true", help="跳过保护直接 SIGKILL")

    args = p.parse_args()

    if args.cmd in (None, "app"):
        from .app import main as app_main
        app_main()
    elif args.cmd == "scan":
        cmd_scan(args)
    elif args.cmd == "history":
        cmd_history(args)
    elif args.cmd == "actions":
        cmd_actions(args)
    elif args.cmd == "kill":
        cmd_kill(args)
    elif args.cmd == "kill-port":
        args.pid = None
        cmd_kill(args)


if __name__ == "__main__":
    main()
