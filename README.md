# PortPilot · 端口哨兵

**Monitor every listening port on your Mac — and kill the ones your AI sessions left behind, with one click.**

用 AI 启动的各种 dev server，页面一关就成了没人管的孤儿进程：端口占着、内存耗着，你还想不起它是谁。PortPilot 常驻菜单栏，自动扫描所有 TCP 监听端口，区分「AI 启动的服务」与「系统/其他服务」，AI 服务点图标即停，全程留痕可回查。

## 功能

- 🤖 **AI 服务识别**：三层规则（工作目录 / 命令特征 / 系统保护名单），uvicorn、vite、`npm run dev`、`http.server`、ekko… 即使跑在 /tmp 也能认出来
- ⏹ **安全的停止动作**：每项服务点开后才出现「⏹ 停止」，不会误触；SIGTERM 优雅停止 → 3 秒未退自动 SIGKILL，整棵进程树连坐
- 🛡 **系统服务防误杀**：`com.apple.*`、Docker、sshd、非当前用户进程、22/5900 端口一律只读，CLI 下也拒绝（`--force` 才可越过）
- 📜 **历史与审计**：SQLite 记录每个端口的起/停事件与每次停止操作，「这个端口是谁什么时候起的」随时可查
- 🔔 **变化通知**：AI 端口新增/消失时 macOS 原生通知（可开关）
- 🖥 **紧凑菜单**：服务按「应用名 + 端口」展示，其他服务折叠进子菜单，整菜单不超过半屏；完整命令行/PID/工作目录在「详情」中查看，可一键跳转配置文件、在 Finder 中打开服务目录

## 安装

从 [Releases](../../releases) 下载 `PortPilot-macOS.zip`，解压拖入「应用程序」。

- 系统要求：macOS 10.15+，Intel 与 Apple Silicon 通用（universal2 单包双架构）
- 首次打开若遇 Gatekeeper 提示：右键 → 打开 → 再点「打开」（未做开发者证书签名，ad-hoc 签名分发）

## 使用

启动后菜单栏出现 `PP·N` 图标（N = 当前 AI 服务数）：

```
🤖 AI 服务（4）— 点开条目操作
   ekko-studio  :8649  ⏹
      ⏹ 停止
      ℹ️ 详情
      📂 在 Finder 中打开
   chat-agent  :8787  ⏹
      …
⚙️ 其他服务（33）           ← 折叠
────────────
立即刷新
最近端口动态
变化通知 ✓
打开配置文件
打开数据目录
退出 PortPilot
```

### CLI（在源码目录下）

```bash
python3 -m portpilot scan            # 扫描（默认隐藏系统服务，--all 全量）
python3 -m portpilot history 50      # 端口出现/消失历史
python3 -m portpilot actions 20      # 停止操作审计
python3 -m portpilot kill-port 8649  # 按端口停止
python3 -m portpilot kill 12345      # 按 PID 停止（受保护进程需 --force）
```

## AI 进程识别规则（`~/.portpilot/config.json`）

1. **工作目录**命中 `watch_dirs`（默认含 `~/Downloads/AIProject` 等，自行增删）→ AI
2. **命令特征**命中 `ai_patterns`（uvicorn / vite / jupyter / npm run dev …）→ AI
3. 命中 `protected_patterns` / 非本用户进程 / 受保护端口 → 系统，拒停

数据（历史与审计）存于 `~/.portpilot/history.db`。

## 从源码构建

```bash
git clone https://github.com/DoubleHeer/PortPilot.git
cd PortPilot
python3 -m venv .venv && .venv/bin/pip install rumps py2app
.venv/bin/python setup.py py2app
codesign --force --deep --sign - dist/PortPilot.app
open dist/PortPilot.app
```

Python 3.9+。CI 会为每个 tag（`v*`）自动构建并发布通用 .app 到 Release。

## 许可

[MIT](LICENSE)
