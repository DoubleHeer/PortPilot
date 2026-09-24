"""配置加载：~/.portpilot/config.json，首次运行自动生成默认配置。"""

import json
import os

CONFIG_DIR = os.path.expanduser("~/.portpilot")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "watch_dirs": [
        "~/Downloads/AIProject",
        "~/wechat-assistant",
        "~/Downloads/AIProject/QwenWork/LocalPort",
    ],
    # 命令行命中即判定为 AI/开发服务
    "ai_patterns": [
        r"uvicorn", r"gunicorn", r"vite", r"webpack", r"next(-server| dev)",
        r"http\.server", r"flask", r"php artisan serve", r"streamlit",
        r"jupyter", r"ekko", r"live-server", r"http-server",
        r"deno (run|serve)", r"bun (run|dev)", r"nodemon", r"tsx watch",
        r"python.*-m.*server", r"node .*server", r"npm run dev",
    ],
    # 命令行命中则视为系统/受保护服务，仅展示不可直接停
    "protected_patterns": [
        r"com\.apple\.", r"/System/Library", r"/usr/libexec", r"/usr/sbin",
        r"com\.docker|Docker\.app", r"rapportd", r"mDNSResponder", r"launchd",
        r"sshd", r"identityservicesd", r"cloudd", r"sharingd", r"controlcenter",
        r"docker-proxy", r"vpn", r"Symantec", r"screencaptureui",
    ],
    # 受保护端口（远程管理等）
    "protected_ports": [22, 5900, 5901],
    "scan_interval": 5,
    "notify": True,
    "notify_only_ai": True,
}


def load_config() -> dict:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # 补齐新增字段
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
