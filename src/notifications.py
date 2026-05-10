"""邮件和桌面通知"""

import smtplib
from email.mime.text import MIMEText


def send_email(cfg, title, content):
    """发送邮件，失败时弹窗提示（需在主线程调用）"""
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
        return True
    except Exception:
        return False


def send_email_silent(cfg, title, content):
    """静默发送邮件，不弹窗"""
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
        return True
    except Exception:
        return False


def send_desktop(title, message):
    """发送桌面通知"""
    try:
        from plyer import notification
        notification.notify(title=title, message=message, timeout=10)
        return True
    except Exception:
        return False
