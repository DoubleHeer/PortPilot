"""SQLite 存储：端口出现/消失事件 + 停止操作审计，库文件 ~/.portpilot/history.db。"""

import os
import sqlite3
import time

DB_PATH = os.path.expanduser("~/.portpilot/history.db")


def conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.execute(
        """CREATE TABLE IF NOT EXISTS events(
            ts REAL, event TEXT, port INTEGER, pid INTEGER,
            name TEXT, category TEXT, cmd TEXT, cwd TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS actions(
            ts REAL, action TEXT, pid INTEGER, port INTEGER,
            name TEXT, detail TEXT)"""
    )
    c.commit()
    return c


def record_events(up_list, down_list):
    """up_list/down_list: Listener 列表"""
    c = conn()
    now = time.time()
    rows = []
    for l in up_list:
        rows.append((now, "up", l.port, l.pid, l.name, l.category, l.command, l.cwd))
    for l in down_list:
        rows.append((now, "down", l.port, l.pid, l.name, l.category, l.command, l.cwd))
    if rows:
        c.executemany(
            "INSERT INTO events(ts,event,port,pid,name,category,cmd,cwd) VALUES(?,?,?,?,?,?,?,?)",
            rows,
        )
        c.commit()
    c.close()


def record_action(action, pid, port, name, detail):
    c = conn()
    c.execute(
        "INSERT INTO actions(ts,action,pid,port,name,detail) VALUES(?,?,?,?,?,?)",
        (time.time(), action, pid, port, name, detail),
    )
    c.commit()
    c.close()


def recent_events(limit=30):
    c = conn()
    rows = c.execute(
        "SELECT ts,event,port,pid,name,category,cmd FROM events ORDER BY ts DESC LIMIT ?",
        (limit,),
    ).fetchall()
    c.close()
    return rows


def recent_actions(limit=20):
    c = conn()
    rows = c.execute(
        "SELECT ts,action,pid,port,name,detail FROM actions ORDER BY ts DESC LIMIT ?",
        (limit,),
    ).fetchall()
    c.close()
    return rows
