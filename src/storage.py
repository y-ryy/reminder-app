"""YAML 操作、对话历史管理"""

import json
import os
from datetime import datetime, date

import yaml

from config import HISTORY_PATH

# ============ 对话历史 ============

MAX_HISTORY = 100


def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"history": []}


def save_history(data):
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_history(role, content, event=None):
    data = load_history()
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "role": role,
        "content": content,
    }
    if event:
        entry["event"] = event
    data["history"].append(entry)
    if len(data["history"]) > MAX_HISTORY:
        data["history"] = data["history"][-MAX_HISTORY:]
    save_history(data)


def clear_history():
    save_history({"history": []})


# ============ YAML 操作 ============

def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"reminders": []}


def save_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def to_date_str(val):
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    return str(val) if val else ""
