"""提醒生成、自动完成、定时检查"""

import sys
import threading
import time
from datetime import datetime, date, timedelta

from config import get_semester_start
from storage import load_yaml, save_yaml
from notifications import send_email


def generate_reminders(rem, semester_start=None):
    """根据事件精度自动生成提醒时间点"""
    if semester_start is None:
        semester_start = date(2026, 3, 2)
    period_hours = {"1-4": 6, "5-8": 10, "evening": 14, "全天": 7}
    reminders = []

    if rem.get("completed"):
        rem["reminders"] = []
        return

    # 只有周次
    if "week" in rem and "date" not in rem and "start" not in rem:
        try:
            week_num = int(rem["week"].replace("第", "").replace("周", ""))
            week_monday = semester_start + timedelta(weeks=week_num - 1)
            prev_monday = week_monday - timedelta(days=7)
            prev_sunday = week_monday - timedelta(days=1)
            reminders.append({"time": f"{prev_monday} 20:00", "sent": False})
            reminders.append({"time": f"{prev_sunday} 20:00", "sent": False})
        except ValueError:
            pass

    # 具体日期
    elif "date" in rem:
        try:
            event_date = datetime.strptime(str(rem["date"]), "%Y-%m-%d")
            day_before = event_date - timedelta(days=1)
            reminders.append({"time": day_before.strftime("%Y-%m-%d") + " 20:00", "sent": False})
            time_val = rem.get("time", "全天")
            hour = period_hours.get(time_val, 7)
            reminders.append({"time": event_date.strftime("%Y-%m-%d") + f" {hour:02d}:00", "sent": False})
        except ValueError:
            pass

    # 多日周期事件
    elif "start" in rem and "end" in rem:
        try:
            start_dt = datetime.strptime(str(rem["start"]), "%Y-%m-%d")
            end_dt = datetime.strptime(str(rem["end"]), "%Y-%m-%d")
            day_before = start_dt - timedelta(days=1)
            reminders.append({"time": day_before.strftime("%Y-%m-%d") + " 20:00", "sent": False})
            d = start_dt
            while d <= end_dt:
                if d.weekday() == 0:
                    reminders.append({"time": d.strftime("%Y-%m-%d") + " 07:30", "sent": False})
                d += timedelta(days=1)
        except ValueError:
            pass

    rem["reminders"] = reminders


def auto_complete_timeout(cfg, data):
    """自动标记已完成的事件：有日期的次日标记，只有周次的下周一标记"""
    now = datetime.now()
    today = now.date()
    changed = False
    semester_start = get_semester_start(cfg)

    for rem in data.get("reminders", []):
        if rem.get("completed"):
            continue

        event_date = rem.get("date") or rem.get("end") or rem.get("start")
        if event_date:
            try:
                event_dt = datetime.strptime(str(event_date), "%Y-%m-%d").date()
                if today > event_dt:
                    rem["completed"] = True
                    rem["completed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    changed = True
            except ValueError:
                pass
        elif rem.get("week"):
            try:
                week_num = int(rem["week"].replace("第", "").replace("周", ""))
                week_monday = semester_start + timedelta(weeks=week_num - 1)
                next_monday = week_monday + timedelta(days=7)
                if today >= next_monday:
                    rem["completed"] = True
                    rem["completed_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
                    changed = True
            except ValueError:
                pass

    if changed:
        save_yaml(cfg["yaml_path"], data, cfg)


def regenerate_reminders(cfg, data):
    """为缺少提醒点的事件自动生成（迁移旧数据）"""
    changed = False
    semester_start = get_semester_start(cfg)
    for rem in data.get("reminders", []):
        if "reminders" not in rem:
            generate_reminders(rem, semester_start)
            changed = True
    if changed:
        save_yaml(cfg["yaml_path"], data, cfg)


def send_startup_reminder(cfg):
    """启动时发送今天和明天的未完成任务汇总"""
    try:
        data = load_yaml(cfg["yaml_path"])
    except Exception as e:
        print(f"[提醒] 启动汇总加载数据失败: {e}", file=sys.stderr)
        return

    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_str = today.strftime("%Y-%m-%d")
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")

    today_tasks = []
    tomorrow_tasks = []
    period_labels = {"1-4": "1~4节", "5-8": "5~8节", "evening": "晚课", "全天": "全天"}

    for rem in data.get("reminders", []):
        if rem.get("completed"):
            continue
        event_date = rem.get("date") or rem.get("start")
        if not event_date:
            continue
        event_date_str = str(event_date)
        name = rem.get("name", "")
        loc = rem.get("location", "")
        time_val = rem.get("time", "")
        time_label = period_labels.get(time_val, time_val) if time_val else ""
        week = rem.get("week", "")
        parts = [f"  - {name}"]
        if loc:
            parts.append(f"地点: {loc}")
        if time_label:
            parts.append(f"时间: {time_label}")
        elif week:
            parts.append(f"周次: {week}")
        line = "  ".join(parts)
        if event_date_str == today_str:
            today_tasks.append(line)
        elif event_date_str == tomorrow_str:
            tomorrow_tasks.append(line)

    if not today_tasks and not tomorrow_tasks:
        return

    lines = ["日程提醒启动报告", ""]
    if today_tasks:
        lines.append(f"【今日任务 {today_str}】")
        lines.extend(today_tasks)
        lines.append("")
    if tomorrow_tasks:
        lines.append(f"【明日任务 {tomorrow_str}】")
        lines.extend(tomorrow_tasks)
    lines.append("")
    lines.append("此邮件由日程提醒工具自动发送")

    message = "\n".join(lines)
    send_email(cfg, f"日程提醒：今日{len(today_tasks)}项 明日{len(tomorrow_tasks)}项", message, silent=True)


def start_reminder_checker(cfg):
    """启动定时提醒检查线程（每60秒检查一次）"""
    threading.Thread(target=_reminder_checker_loop, args=(cfg,), daemon=True).start()


def _reminder_checker_loop(cfg):
    """定时提醒检查循环"""
    while True:
        time.sleep(60)
        try:
            _check_due_reminders(cfg)
        except Exception as e:
            print(f"[提醒] 检查提醒时出错: {e}", file=sys.stderr)


def _check_due_reminders(cfg):
    """检查并发送到期的定时提醒（补发错过的提醒）"""
    try:
        data = load_yaml(cfg["yaml_path"])
    except Exception as e:
        print(f"[提醒] 加载数据失败: {e}", file=sys.stderr)
        return

    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M")
    changed = False
    period_labels = {"1-4": "1~4节", "5-8": "5~8节", "evening": "晚课", "全天": "全天"}

    for rem in data.get("reminders", []):
        if not rem.get("reminders"):
            continue
        for reminder in rem["reminders"]:
            if reminder.get("sent"):
                continue
            reminder_time = reminder.get("time", "")
            if reminder_time <= now_str:
                name = rem.get("name", "")
                loc = rem.get("location", "")
                event_date = rem.get("date") or rem.get("start") or ""
                time_val = rem.get("time", "")
                time_label = period_labels.get(time_val, time_val) if time_val else ""
                week = rem.get("week", "")
                parts = [f"事项：{name}"]
                if loc:
                    parts.append(f"地点：{loc}")
                if event_date:
                    parts.append(f"日期：{event_date}")
                if time_label:
                    parts.append(f"时段：{time_label}")
                elif week:
                    parts.append(f"周次：{week}")
                parts.append("\n此邮件由日程提醒工具自动发送")
                message = "\n".join(parts)
                send_email(cfg, f"日程提醒：{name}", message, silent=True)
                reminder["sent"] = True
                changed = True

    if changed:
        save_yaml(cfg["yaml_path"], data, cfg)
