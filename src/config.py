"""配置管理、常量、文件IO"""

import json
import os
from datetime import date, datetime

# ============ 路径 ============

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
HISTORY_PATH = os.path.join(DATA_DIR, "chat_history.json")
NOTIFICATION_HISTORY_PATH = os.path.join(DATA_DIR, "notification_history.json")

# ============ 常量 ============

AI_PROVIDERS = {
    "zhipu": {
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "models": [
            {"id": "glm-4-flash", "name": "glm-4-flash（免费）", "free": True},
            {"id": "glm-4", "name": "glm-4", "free": False},
            {"id": "glm-4v", "name": "glm-4v", "free": False},
        ],
        "default_model": "glm-4-flash"
    },
    "qwen": {
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "models": [
            {"id": "qwen-turbo", "name": "qwen-turbo（免费）", "free": True},
            {"id": "qwen-plus", "name": "qwen-plus", "free": False},
        ],
        "default_model": "qwen-turbo"
    }
}

DEFAULT_CONFIG = {
    "yaml_path": "",
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465,
    "sender_email": "",
    "sender_password": "",
    "receiver_email": "",
    "ai_provider": "zhipu",
    "ai_model": "glm-4-flash",
    "ai_api_key": "",
    "enable_email": True,
    "enable_desktop": True,
    "minimize_to_tray": False,
    "semester_start": "2026-03-02",
    "export_md_path": "",
}

# ============ 配置读写 ============

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_semester_start(cfg):
    """从配置中获取学期起始日，返回 date 对象"""
    val = cfg.get("semester_start", "2026-03-02")
    return datetime.strptime(str(val), "%Y-%m-%d").date()
