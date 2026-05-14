"""YAML 操作、对话历史管理、通知历史"""

import json
import os
import re
import threading
from datetime import datetime, date, timedelta

import yaml

from config import HISTORY_PATH, NOTIFICATION_HISTORY_PATH

# ============ YAML 锁 ============

_yaml_lock = threading.Lock()

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
    with _yaml_lock:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"reminders": []}


def save_yaml(path, data, cfg=None):
    with _yaml_lock:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    if cfg and cfg.get("export_md_path"):
        try:
            export_to_md(data, cfg["export_md_path"])
        except Exception as e:
            print(f"[导出] MD 导出失败: {e}", file=__import__("sys").stderr)


def to_date_str(val):
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    return str(val) if val else ""


# ============ 通知历史 ============

MAX_NOTIFICATION_HISTORY = 200


def add_notification_history(title, message):
    data = load_notification_history()
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": title,
        "message": message,
    }
    data["history"].append(entry)
    if len(data["history"]) > MAX_NOTIFICATION_HISTORY:
        data["history"] = data["history"][-MAX_NOTIFICATION_HISTORY:]
    os.makedirs(os.path.dirname(NOTIFICATION_HISTORY_PATH), exist_ok=True)
    with open(NOTIFICATION_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_notification_history():
    if os.path.exists(NOTIFICATION_HISTORY_PATH):
        with open(NOTIFICATION_HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"history": []}


# ============ MD 导出 ============

TYPE_CN = {"exam": "考试", "class": "上课", "training": "实训", "other": "其他"}


def _parse_week(week_str):
    """从 '第8周' 中提取数字，提取失败返回 9999"""
    m = re.search(r"(\d+)", str(week_str))
    return int(m.group(1)) if m else 9999


def _md_get_completed(event, sub_date_str):
    """检查子项完成状态"""
    completed_sub = event.get("completed_sub_dates") or []
    if sub_date_str in completed_sub:
        return True
    if not completed_sub and event.get("completed"):
        return True
    return False


def _get_export_filename(export_dir):
    """生成导出文件名：日程MMDD.md，同日多次追加 _01 _02 ..."""
    today_str = datetime.now().strftime("%m%d")
    base = f"日程{today_str}"
    candidate = os.path.join(export_dir, f"{base}.md")
    if not os.path.exists(candidate):
        return candidate
    i = 1
    while True:
        candidate = os.path.join(export_dir, f"{base}_{i:02d}.md")
        if not os.path.exists(candidate):
            return candidate
        i += 1


def export_to_md(data, export_dir):
    """将日程数据导出为 Markdown 文件，每次生成独立文件"""
    reminders = data.get("reminders", [])

    date_events = []
    week_events = []
    multi_details = []

    for event in reminders:
        name = event.get("name", "未命名")
        etype = TYPE_CN.get(event.get("type", ""), "其他")
        location = event.get("location", "").strip() or "—"

        if "schedule" in event and "start" in event:
            start = to_date_str(event["start"])
            end = to_date_str(event.get("end", event["start"]))
            try:
                start_d = datetime.strptime(start, "%Y-%m-%d").date()
                end_d = datetime.strptime(end, "%Y-%m-%d").date()
            except ValueError:
                continue

            subs = []
            done = 0
            cur = start_d
            while cur <= end_d:
                wd = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][cur.weekday()]
                for entry in event.get("schedule", []):
                    if entry.get("day") == wd:
                        is_done = _md_get_completed(event, cur.strftime("%Y-%m-%d"))
                        period = entry.get("period", "全天")
                        loc = entry.get("location", "").strip() or location
                        chk = "x" if is_done else " "
                        subs.append(f"- [{chk}] {cur.strftime('%m-%d')} {wd} {period} {loc}")
                        if is_done:
                            done += 1
                cur += timedelta(days=1)

            status = f"{done}/{len(subs)}" if subs else "—"
            date_events.append((start, f"| {start} ~ {end} | {name} | {etype} | {location} | {status} |"))

            if subs:
                multi_details.append(f"\n#### {name} ({start} ~ {end})")
                multi_details.extend(subs)

        elif "date" in event:
            d = to_date_str(event["date"])
            is_done = event.get("completed", False)
            status = "✅" if is_done else "⬜"
            strike = f"~~{name}~~" if is_done else name
            date_events.append((d, f"| {d} | {strike} | {etype} | {location} | {status} |"))

        elif "week" in event:
            w = event["week"]
            wn = _parse_week(w)
            is_done = event.get("completed", False)
            strike = f"~~{name}~~" if is_done else name
            week_events.append((wn, f"| {w} | {strike} | {etype} | {location} |"))

    date_events.sort(key=lambda x: x[0])
    week_events.sort(key=lambda x: x[0])

    lines = [
        "# 我的日程\n",
        f"> 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
    ]

    if date_events:
        lines.append("## 有日期的事件\n")
        lines.append("| 日期 | 事项 | 类型 | 地点 | 状态 |")
        lines.append("|------|------|------|------|------|")
        for _, row in date_events:
            lines.append(row)

    if multi_details:
        lines.append("\n## 多日事件详情")
        lines.extend(multi_details)

    if week_events:
        lines.append("\n## 仅有周次\n")
        lines.append("| 周次 | 事项 | 类型 | 地点 |")
        lines.append("|------|------|------|------|")
        for _, row in week_events:
            lines.append(row)

    if not date_events and not week_events:
        lines.append("\n*暂无日程*\n")

    os.makedirs(export_dir, exist_ok=True)
    md_path = _get_export_filename(export_dir)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
