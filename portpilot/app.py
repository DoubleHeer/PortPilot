"""菜单栏主程序：rumps 驱动，定时扫描 + 变化通知 + 一键停止。

菜单设计（控制高度 ≤ 半屏）：
- 每个服务是一个子菜单父项（显示 应用名+端口+⏹），点开才有"停止"动作，避免误触
- 其他服务整体折叠进子菜单；两类列表都有条数上限，超出提示用 CLI 查看
- 详情窗口可查看完整命令行/工作目录/PID
"""

import html
import os
import subprocess
import time as _time

import rumps

from . import killer, scanner, store
from .config import CONFIG_PATH, load_config, save_config

VIEW_DIR = os.path.expanduser("~/.portpilot/views")


def _open_view(filename: str, title: str, body_html: str):
    """生成 HTML 视图并用默认浏览器打开（非模态：可自由关闭/滚动，无焦点问题）。"""
    os.makedirs(VIEW_DIR, exist_ok=True)
    page = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body{{background:#1e1e2e;color:#cdd6f4;font:14px/1.7 -apple-system,"PingFang SC",sans-serif;
margin:0;padding:24px 32px;}}
h1{{font-size:16px;color:#89b4fa;margin:0 0 16px;}}
table{{border-collapse:collapse;width:100%;}}
td{{padding:4px 10px 4px 0;vertical-align:top;white-space:nowrap;}}
td.full{{white-space:normal;word-break:break-all;}}
.mono{{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;}}
.up{{color:#a6e3a1;}} .down{{color:#f38ba8;}} .dim{{color:#6c7086;}}
.tag{{display:inline-block;padding:0 8px;border-radius:4px;font-size:11px;}}
.tag-ai{{background:#45475a;color:#a6e3a1;}} .tag-other{{background:#45475a;color:#f9e2af;}}
.tag-protected{{background:#45475a;color:#f38ba8;}}
</style></head><body><h1>{html.escape(title)}</h1>{body_html}</body></html>"""
    path = os.path.join(VIEW_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    subprocess.Popen(["open", path])


def _confirm(title: str, message: str, ok_button: str = "停止") -> bool:
    """系统级确认框（osascript 独立进程弹窗，焦点可靠，不依赖本应用激活状态）。"""
    esc = message.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    script = (f'display dialog "{esc}" with title "{title}" '
              f'buttons {{"取消", "{ok_button}"}} default button "取消" '
              f'cancel button "取消" with icon caution')
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.returncode == 0

AI_CAP = 12       # 主菜单 AI 服务最多展示条数（控制菜单高度）
OTHER_CAP = 15    # "其他服务"子菜单最多展示条数
STOP_ICON = "⏹"
DETAIL_ICON = "ℹ️"
FOLDER_ICON = "📂"
CONFIRM_MARK = " ⚠️需确认"


def _app_label(l) -> str:
    """友好应用名：工作目录名 > 进程名。"""
    if l.cwd:
        return os.path.basename(l.cwd.rstrip("/")) or l.name
    return l.name


class PortPilotApp(rumps.App):
    def __init__(self):
        super().__init__(name="PortPilot", title="PP·…", quit_button="退出 PortPilot")
        self.config = load_config()
        self.prev = {}  # (pid, port) -> Listener
        self._menu_sig = None
        rumps.Timer(self.refresh, self.config.get("scan_interval", 5)).start()

    # ---------- 核心刷新 ----------
    def refresh(self, _=None):
        try:
            listeners = scanner.scan_listeners(self.config)
        except Exception as e:
            self.title = "PP!"
            rumps.logger.error(f"scan failed: {e}")
            return

        cur = {l.key: l for l in listeners}
        up = [cur[k] for k in cur if k not in self.prev]
        down = [self.prev[k] for k in self.prev if k not in cur]
        if up or down:
            try:
                store.record_events(up, down)
            except Exception:
                pass
            self._notify_changes(up, down)

        n_ai = sum(1 for l in listeners if l.category == "ai")
        self.title = f"PP·{n_ai}" if n_ai else "PP"

        self.prev = cur
        sig = tuple(sorted((l.pid, l.port, l.category, l.name) for l in listeners))
        if sig != self._menu_sig:
            self._menu_sig = sig
            self._rebuild_menu(listeners)

    # ---------- 变化通知 ----------
    def _notify_changes(self, up, down):
        if not self.config.get("notify", True):
            return
        only_ai = self.config.get("notify_only_ai", True)
        try:
            for l in up:
                if only_ai and l.category != "ai":
                    continue
                rumps.notification("PortPilot", "新服务监听",
                                   f":{l.port}  {_app_label(l)}")
            for l in down:
                if only_ai and l.category != "ai":
                    continue
                rumps.notification("PortPilot", "服务已停止",
                                   f":{l.port}  {_app_label(l)}")
        except Exception:
            pass  # 通知失败不影响主流程

    # ---------- 菜单 ----------
    def _rebuild_menu(self, listeners):
        menu = self.menu
        menu.clear()

        ai = [l for l in listeners if l.category == "ai"]
        others = [l for l in listeners if l.category != "ai"]

        header = rumps.MenuItem(f"🤖 AI 服务（{len(ai)}）— 点开条目操作")
        header.set_callback(None)
        menu.add(header)
        if not ai:
            none = rumps.MenuItem("  暂无 AI 服务监听")
            none.set_callback(None)
            menu.add(none)
        for l in ai[:AI_CAP]:
            menu.add(self._service_item(l))
        if len(ai) > AI_CAP:
            more = rumps.MenuItem(f"  …还有 {len(ai) - AI_CAP} 个，CLI 查看: portpilot scan")
            more.set_callback(None)
            menu.add(more)

        other_menu = rumps.MenuItem(f"⚙️ 其他服务（{len(others)}）")
        other_menu.set_callback(None)
        if not others:
            sub = rumps.MenuItem("  暂无")
            sub.set_callback(None)
            other_menu.add(sub)
        for l in others[:OTHER_CAP]:
            other_menu.add(self._service_item(l))
        if len(others) > OTHER_CAP:
            more = rumps.MenuItem(f"  …还有 {len(others) - OTHER_CAP} 个")
            more.set_callback(None)
            other_menu.add(more)
        menu.add(other_menu)

        menu.add(rumps.separator)
        menu.add(rumps.MenuItem("立即刷新", callback=self.refresh))
        menu.add(rumps.MenuItem("最近端口动态", callback=self.show_history))
        self.notify_item = rumps.MenuItem("变化通知", callback=self.toggle_notify)
        self.notify_item.state = bool(self.config.get("notify", True))
        menu.add(self.notify_item)
        menu.add(rumps.separator)
        menu.add(rumps.MenuItem("打开配置文件", callback=self.open_config))
        menu.add(rumps.MenuItem("打开数据目录", callback=self.open_datadir))
        # menu.clear() 会把 rumps 自动生成的退出项一并清掉，这里必须显式补回
        menu.add(rumps.separator)
        menu.add(rumps.MenuItem("退出 PortPilot",
                                callback=lambda _s: rumps.quit_application()))

    def _service_item(self, l) -> rumps.MenuItem:
        """服务条目：父项=应用名+端口+⏹，子菜单=停止/详情/Finder。"""
        label = f"{_app_label(l)}  :{l.port}"
        parent = rumps.MenuItem(label + ("  ⏹" if l.category != "protected" else ""))
        parent.set_callback(None)  # 点击父项只展开子菜单，不执行动作

        if l.category != "protected":
            mark = CONFIRM_MARK if l.category != "ai" else ""
            parent.add(rumps.MenuItem(f"{STOP_ICON} 停止{mark}",
                                      callback=lambda _s, _l=l: self.on_stop(_l)))
        parent.add(rumps.MenuItem(f"{DETAIL_ICON} 详情",
                                  callback=lambda _s, _l=l: self.show_detail(_l)))
        if l.cwd:
            parent.add(rumps.MenuItem(f"{FOLDER_ICON} 在 Finder 中打开",
                                      callback=lambda _s, _l=l: self.reveal_cwd(_l)))
        return parent

    # ---------- 动作 ----------
    def on_stop(self, l):
        if l.key not in self.prev:
            rumps.notification("PortPilot", "无需操作", f":{l.port} 已停止")
            self.refresh()
            return
        if l.category != "ai":
            msg = (f":{l.port}  {_app_label(l)}\n\n{l.command[:200]}")
            if not _confirm("确认停止该服务？", msg):
                return
        ok, detail = killer.stop(l.pid, l.port, l.name)
        rumps.notification("PortPilot",
                           "已停止" if ok else "停止失败",
                           f":{l.port}  {_app_label(l)}\n{detail}")
        self.refresh()

    def show_detail(self, l):
        """详情页（浏览器打开）：完整命令行 / 工作目录 / PID 等。"""
        cat = {"ai": "AI 服务", "other": "其他服务", "protected": "系统服务"}[l.category]
        rows = [
            ("应用", html.escape(_app_label(l))),
            ("端口", f":{l.port}"),
            ("分类", cat),
            ("PID", str(l.pid)),
            ("工作目录", html.escape(l.cwd or "（不可见）")),
        ]
        tr = "".join(f'<tr><td class="dim">{k}</td><td class="mono">{v}</td></tr>'
                     for k, v in rows)
        tr += (f'<tr><td class="dim">完整命令行</td>'
               f'<td class="mono full">{html.escape(l.command)}</td></tr>')
        _open_view(f"detail-{l.pid}-{l.port}.html",
                   f"PortPilot · :{l.port} 详情", f"<table>{tr}</table>")

    def reveal_cwd(self, l):
        if l.cwd and os.path.isdir(l.cwd):
            subprocess.Popen(["open", l.cwd])
        else:
            rumps.notification("PortPilot", "无法打开", "工作目录不可见")

    def show_history(self, sender):
        """端口动态页（浏览器打开）：最近 30 条起/停事件，可滚动查看完整命令行。"""
        rows = store.recent_events(50)
        if not rows:
            _open_view("history.html", "PortPilot · 端口动态",
                       "<p class='dim'>暂无记录</p>")
            return
        trs = []
        for ts, ev, port, pid, name, cat, cmd in rows:
            t = _time.strftime("%m-%d %H:%M:%S", _time.localtime(ts))
            mark = ('<span class="up">↑起</span>' if ev == "up"
                    else '<span class="down">↓停</span>')
            cat_zh = {"ai": "AI", "other": "其他", "protected": "系统"}.get(cat, cat)
            tag = f'<span class="tag tag-{cat}">{cat_zh}</span>'
            trs.append(
                f'<tr><td class="dim mono">{t}</td><td>{mark}</td>'
                f'<td class="mono">:{port}</td><td>{tag}</td>'
                f'<td class="mono full">{html.escape(cmd)}</td></tr>')
        body = ("<table><tr class='dim'><td>时间</td><td></td><td>端口</td>"
                "<td>分类</td><td>命令行</td></tr>" + "".join(trs) + "</table>")
        _open_view("history.html", "PortPilot · 端口动态（最近 50 条）", body)

    def toggle_notify(self, sender):
        sender.state = not sender.state
        self.config["notify"] = sender.state
        save_config(self.config)

    def open_config(self, sender):
        load_config()  # 确保存在
        subprocess.Popen(["open", CONFIG_PATH])

    def open_datadir(self, sender):
        load_config()
        subprocess.Popen(["open", os.path.dirname(CONFIG_PATH)])


def main():
    PortPilotApp().run()
