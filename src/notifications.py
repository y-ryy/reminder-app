"""邮件和桌面通知"""

import sys
import smtplib
from email.mime.text import MIMEText

from storage import add_notification_history


def send_email(cfg, title, content, silent=False):
    """发送邮件。silent=True 时静默返回 False，否则也返回 False（调用方可自行弹窗）"""
    if not cfg.get("enable_email", True):
        return False
    try:
        msg = MIMEText(content, "plain", "utf-8")
        msg["From"] = cfg["sender_email"]
        msg["To"] = cfg["receiver_email"]
        msg["Subject"] = title
        with smtplib.SMTP_SSL(cfg["smtp_server"], int(cfg["smtp_port"])) as server:
            server.login(cfg["sender_email"], cfg["sender_password"])
            server.sendmail(cfg["sender_email"], cfg["receiver_email"], msg.as_string())
        add_notification_history(title, f"[邮件] {content[:100]}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[通知] 邮件认证失败: {e}", file=sys.stderr)
        return False
    except smtplib.SMTPException as e:
        print(f"[通知] 邮件发送失败: {e}", file=sys.stderr)
        return False
    except (ConnectionError, TimeoutError, OSError) as e:
        print(f"[通知] 网络错误: {e}", file=sys.stderr)
        return False


def send_desktop(title, message):
    """发送桌面通知"""
    try:
        from plyer import notification
        notification.notify(title=title, message=message, timeout=10)
        add_notification_history(title, f"[桌面] {message[:100]}")
        return True
    except ImportError:
        print("[通知] plyer 未安装，桌面通知不可用", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[通知] 桌面通知失败: {e}", file=sys.stderr)
        return False
