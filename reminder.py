"""
日程提醒工具
功能：读取日程.yaml，按规则计算今日需发送的提醒，通过桌面通知 + 邮箱推送
使用：python reminder.py          # 检查并发送今日提醒
      python reminder.py --list   # 查看未来7天的日程
      python reminder.py --test   # 发送一条测试通知
"""

import yaml
import smtplib
import argparse
import json
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta

# ============ 配置 ============

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError("config.json 不存在，请复制 config.example.json 并填写配置")


cfg = load_config()
SMTP_SERVER = cfg["smtp_server"]
SMTP_PORT = cfg["smtp_port"]
SENDER_EMAIL = cfg["sender_email"]
SENDER_PASSWORD = cfg["sender_password"]
RECEIVER_EMAIL = cfg["receiver_email"]
YAML_PATH = cfg["yaml_path"]

# 节次 → 提醒时间
PERIOD_TIMES = {
    "1-4":   {"start": "08:00", "notify": "07:00", "label": "1~4节"},
    "5-8":   {"start": "14:00", "notify": "13:00", "label": "5~8节"},
    "evening": {"start": "19:00", "notify": "18:00", "label": "晚课"},
    "全天":   {"start": "08:00", "notify": "07:00", "label": "全天"},
}

WEEKDAY_MAP = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}


# ============ 工具函数 ============

def load_yaml():
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


SEMESTER_START = date(2026, 3, 2)  # 第1周周一


def to_date(val):
    """将 YAML 中的日期值统一转为 date 对象"""
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return datetime.strptime(val, "%Y-%m-%d").date()
    raise ValueError(f"无法解析日期: {val}")


def get_week_number(d):
    """获取日期所在的学期周数（以第1周周一为基准）"""
    return (d - SEMESTER_START).days // 7 + 1


def is_week_match(week_str, target_date):
    """判断 target_date 是否在 week_str 指定的那一周"""
    try:
        week_num = int(week_str.replace("第", "").replace("周", ""))
        return get_week_number(target_date) == week_num
    except (ValueError, AttributeError):
        return False


def get_prev_week_weekday(weekday_name, week_offset=0):
    """获取上一周的某个星期几的日期"""
    today = date.today()
    target_weekday = WEEKDAY_MAP[weekday_name]
    current_weekday = today.weekday()
    days_since = (current_weekday - target_weekday) % 7
    if days_since == 0:
        days_since = 7
    return today - timedelta(days=days_since + 7 * week_offset)


def get_week_monday(d):
    """获取某日期所在周的周一"""
    return d - timedelta(days=d.weekday())


def format_countdown(target_date, today):
    """生成倒计时文字"""
    delta = (target_date - today).days
    if delta == 0:
        return "就是今天"
    elif delta == 1:
        return "明天"
    elif delta == 2:
        return "后天"
    else:
        return f"还有{delta}天"


def format_reminder_name(rem):
    """格式化提醒事项名称"""
    name = rem["name"]
    if "start" in rem and "end" in rem:
        return f"{name}（{rem['start']} ~ {rem['end']}）"
    elif "date" in rem:
        return f"{name}（{rem['date']}）"
    return name


def send_desktop(title, message):
    """发送桌面通知"""
    try:
        from plyer import notification
        notification.notify(title=title, message=message, timeout=10)
        print(f"  [桌面] {title}: {message}")
    except Exception as e:
        print(f"  [桌面] 发送失败: {e}")


def send_email(title, content):
    """发送邮件通知"""
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = f"日程提醒：{title}"
        msg.attach(MIMEText(content, "plain", "utf-8"))

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"  [邮件] 发送成功")
    except Exception as e:
        print(f"  [邮件] 发送失败: {e}")


def notify(title, message):
    """同时发送桌面通知和邮件"""
    print(f"\n>>> {title}")
    send_desktop(title, message)
    send_email(title, message)


# ============ 提醒规则 ============

def get_today_reminders(reminders):
    """根据规则计算今天需要发送的提醒"""
    today = date.today()
    results = []

    for rem in reminders:
        name = format_reminder_name(rem)
        rem_type = rem.get("type", "other")
        is_exam = rem_type == "exam"

        # 规则1：周提醒 — 前一周周一 + 前一周周五
        if "week" in rem:
            week_str = rem["week"]
            try:
                week_num = int(week_str.replace("第", "").replace("周", ""))
                prev_week = week_num - 1
                semester_start = SEMESTER_START
                prev_monday = semester_start + timedelta(weeks=prev_week - 1, days=0)
                prev_friday = semester_start + timedelta(weeks=prev_week - 1, days=4)
                if today == prev_monday:
                    results.append((name, f"[提前一周·周一] {name} 在 {week_str}，请提前准备"))
                if today == prev_friday:
                    results.append((name, f"[提前一周·周五] {name} 在 {week_str}，下周注意"))
            except ValueError:
                pass

        # 规则2：日期提醒 — 提前3天 + 当天早上（考试类加前7天）
        if "date" in rem:
            try:
                target = to_date(rem["date"])
                days_before = (target - today).days

                if is_exam and days_before == 7:
                    results.append((name, f"[还剩7天] {name}，请开始复习"))
                if days_before == 3:
                    results.append((name, f"[还剩3天] {name}"))
                if days_before == 0:
                    results.append((name, f"[就是今天] {name}，请做好准备"))
            except (ValueError, TypeError):
                pass

        # 规则3：课程提醒 — 前一天 + 课前1小时（基于 schedule）
        if "schedule" in rem and "start" in rem and "end" in rem:
            try:
                start = to_date(rem["start"])
                end = to_date(rem["end"])
                end_inclusive = end + timedelta(days=1)

                for entry in rem["schedule"]:
                    entry_weekday = WEEKDAY_MAP.get(entry["day"])
                    if entry_weekday is None:
                        continue

                    period = entry.get("period", "全天")
                    period_info = PERIOD_TIMES.get(period, PERIOD_TIMES["全天"])
                    location = entry.get("location", "")

                    # 遍历日期范围，找出匹配的天
                    d = start
                    while d < end_inclusive:
                        if d.weekday() == entry_weekday:
                            days_before = (d - today).days
                            loc_str = f" @{location}" if location else ""

                            # 前一天通知
                            if days_before == 1:
                                results.append((
                                    name,
                                    f"[明天] {name} - {entry['day']} {period_info['label']}{loc_str}"
                                ))

                            # 当天课前通知
                            if days_before == 0:
                                results.append((
                                    name,
                                    f"[今天] {name} - {entry['day']} {period_info['label']}{loc_str}"
                                ))
                        d += timedelta(days=1)
            except (ValueError, KeyError):
                pass

        # 规则4：晚间事项 — 前一天 + 当天18:00
        if rem.get("time") == "evening" and "date" in rem:
            try:
                target = to_date(rem["date"])
                days_before = (target - today).days
                if days_before == 1:
                    results.append((name, f"[明天晚上] {name}"))
                if days_before == 0:
                    results.append((name, f"[今晚] {name}"))
            except ValueError:
                pass

    return results


# ============ 命令行功能 ============

def list_upcoming(days=7):
    """列出未来 N 天的日程"""
    data = load_yaml()
    today = date.today()
    end_date = today + timedelta(days=days)
    upcoming = []

    for rem in data.get("reminders", []):
        name = rem["name"]
        loc = rem.get("location", "")

        if "date" in rem:
            try:
                d = to_date(rem["date"])
                if today <= d <= end_date:
                    loc_str = f" @{loc}" if loc else ""
                    countdown = format_countdown(d, today)
                    upcoming.append((d, f"{name} — {d.strftime('%m/%d %A')}（{countdown}）{loc_str}"))
            except ValueError:
                pass

        if "schedule" in rem and "start" in rem:
            try:
                start = to_date(rem["start"])
                end = to_date(rem["end"])
                end_inclusive = end + timedelta(days=1)
                d = start
                while d < end_inclusive:
                    if today <= d <= end_date:
                        for entry in rem.get("schedule", []):
                            if d.weekday() == WEEKDAY_MAP.get(entry["day"], -1):
                                e_loc = entry.get("location", "")
                                loc_str = f" @{e_loc}" if e_loc else ""
                                period_info = PERIOD_TIMES.get(entry.get("period", "全天"), PERIOD_TIMES["全天"])
                                countdown = format_countdown(d, today)
                                upcoming.append((d, f"{name} — {d.strftime('%m/%d')} {entry['day']} {period_info['label']}（{countdown}）{loc_str}"))
                    d += timedelta(days=1)
            except ValueError:
                pass

    upcoming.sort(key=lambda x: x[0])
    print(f"\n未来 {days} 天日程：")
    if not upcoming:
        print("  无")
    for _, line in upcoming:
        print(f"  {line}")


def send_test():
    """发送测试通知"""
    notify("测试通知", "这是一条测试消息，确认推送功能正常工作")


# ============ 主程序 ============

def main():
    parser = argparse.ArgumentParser(description="日程提醒工具")
    parser.add_argument("--list", action="store_true", help="查看未来7天日程")
    parser.add_argument("--test", action="store_true", help="发送测试通知")
    args = parser.parse_args()

    if args.test:
        send_test()
        return

    if args.list:
        list_upcoming()
        return

    # 默认：检查并发送今日提醒
    data = load_yaml()
    reminders = data.get("reminders", [])
    today_str = date.today().strftime("%Y-%m-%d")

    print(f"检查日期：{today_str}")
    results = get_today_reminders(reminders)

    if not results:
        print("今日无需提醒的事项")
        return

    print(f"共 {len(results)} 条提醒")
    for title, message in results:
        notify(title, message)

    print("\n全部提醒已发送")


if __name__ == "__main__":
    main()
