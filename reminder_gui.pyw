"""
日程提醒工具 - 图形化界面
功能：查看/管理日程事件，修改配置（YAML路径、邮箱设置）
"""

import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date, timedelta
import yaml

# ============ 配置文件路径 ============

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "yaml_path": "",
    "smtp_server": "smtp.qq.com",
    "smtp_port": 465,
    "sender_email": "",
    "sender_password": "",
    "receiver_email": "",
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


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


# ============ GUI ============

class ReminderApp:
    def __init__(self):
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.title("日程提醒工具")
        self.root.geometry("860x520")
        self.root.resizable(True, True)

        self._build_ui()
        self._load_events()

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)

        # ---- 事件列表页 ----
        self.frame_events = ttk.Frame(notebook)
        notebook.add(self.frame_events, text="事件列表")
        self._build_events_tab()

        # ---- 设置页 ----
        self.frame_settings = ttk.Frame(notebook)
        notebook.add(self.frame_settings, text="设置")
        self._build_settings_tab()

    # ---------- 事件列表 ----------

    def _build_events_tab(self):
        cols = ("type", "date", "week", "location")
        self.tree = ttk.Treeview(self.frame_events, columns=cols, show="tree headings", height=15)
        self.tree.heading("#0", text="事项名称")
        self.tree.heading("type", text="类型")
        self.tree.heading("date", text="日期")
        self.tree.heading("week", text="周次")
        self.tree.heading("location", text="地点")
        self.tree.column("#0", width=220)
        self.tree.column("type", width=60, anchor="center")
        self.tree.column("date", width=110)
        self.tree.column("week", width=110)
        self.tree.column("location", width=240)

        scrollbar = ttk.Scrollbar(self.frame_events, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        scrollbar.pack(side="left", fill="y", pady=6, padx=(0, 6))

        # 右键菜单
        self.ctx_menu = tk.Menu(self.tree, tearoff=0)
        self.ctx_menu.add_command(label="添加", command=self._add_event)
        self.ctx_menu.add_command(label="编辑", command=self._edit_event)
        self.ctx_menu.add_command(label="删除", command=self._delete_event)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="刷新", command=self._load_events)
        self.ctx_menu.add_command(label="测试推送", command=self._test_push)
        self.tree.bind("<Button-3>", self._show_ctx_menu)

    def _load_events(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._rem_index_map = {}  # tree_item_id → reminder_index
        try:
            data = load_yaml(self.cfg["yaml_path"])
        except FileNotFoundError:
            messagebox.showwarning("提示", f"YAML 文件不存在：\n{self.cfg['yaml_path']}")
            return
        except Exception as e:
            messagebox.showerror("错误", f"读取 YAML 失败：{e}")
            return

        SEMESTER_START = date(2026, 3, 2)
        WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday_map = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}
        type_labels = {"exam": "考试", "class": "上课", "training": "实训", "other": "其他"}
        period_labels = {"1-4": "1~4节", "5-8": "5~8节", "evening": "晚课", "全天": "全天"}

        def calc_week(d):
            """从日期计算 第N周周X"""
            week_num = (d - SEMESTER_START).days // 7 + 1
            return f"第{week_num}周{WEEKDAY_NAMES[d.weekday()]}"

        for idx, rem in enumerate(data.get("reminders", [])):
            name = rem.get("name", "")
            rtype = type_labels.get(rem.get("type", ""), rem.get("type", ""))
            loc = rem.get("location", "")

            # 有 schedule 的多日事件 → 折叠展示
            if "schedule" in rem and "start" in rem and "end" in rem:
                start = to_date_str(rem["start"])
                end = to_date_str(rem["end"])
                week = rem.get("week", "")
                parent_id = self.tree.insert("", "end", text=name,
                                             values=(rtype, f"{start} ~ {end}", week, loc))
                self._rem_index_map[parent_id] = idx

                try:
                    start_d = datetime.strptime(start, "%Y-%m-%d").date()
                    end_d = datetime.strptime(end, "%Y-%m-%d").date()
                except ValueError:
                    continue

                for entry in rem.get("schedule", []):
                    entry_wd = weekday_map.get(entry.get("day"))
                    period = entry.get("period", "全天")
                    entry_loc = entry.get("location", loc)
                    period_label = period_labels.get(period, period)

                    if entry_wd is not None:
                        d = start_d
                        while d <= end_d:
                            if d.weekday() == entry_wd:
                                child_id = self.tree.insert(
                                    parent_id, "end",
                                    text=f"{entry['day']} {period_label}",
                                    values=("", d.strftime("%Y-%m-%d"), calc_week(d), entry_loc))
                                self._rem_index_map[child_id] = idx
                            d += timedelta(days=1)
            else:
                # 单日 / 仅周次事件
                date_str = ""
                week_str = rem.get("week", "")
                if "date" in rem:
                    date_str = to_date_str(rem["date"])
                    if not week_str:
                        try:
                            d = datetime.strptime(date_str, "%Y-%m-%d").date()
                            week_str = calc_week(d)
                        except ValueError:
                            pass
                item_id = self.tree.insert("", "end", text=name,
                                           values=(rtype, date_str, week_str, loc))
                self._rem_index_map[item_id] = idx

    def _show_ctx_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        self.ctx_menu.post(event.x_root, event.y_root)

    def _get_selected_reminder_index(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一条事件")
            return None
        return self._rem_index_map.get(sel[0])

    def _add_event(self):
        EventDialog(self.root, "添加事件", callback=self._save_new_event)

    def _save_new_event(self, rem):
        data = load_yaml(self.cfg["yaml_path"])
        data.setdefault("reminders", []).append(rem)
        save_yaml(self.cfg["yaml_path"], data)
        self._load_events()

    def _edit_event(self):
        idx = self._get_selected_reminder_index()
        if idx is None:
            return
        data = load_yaml(self.cfg["yaml_path"])
        rem = data["reminders"][idx]
        EventDialog(self.root, "编辑事件", reminder=rem,
                    callback=lambda r: self._save_edited_event(idx, r))

    def _save_edited_event(self, idx, rem):
        data = load_yaml(self.cfg["yaml_path"])
        data["reminders"][idx] = rem
        save_yaml(self.cfg["yaml_path"], data)
        self._load_events()

    def _delete_event(self):
        idx = self._get_selected_reminder_index()
        if idx is None:
            return
        data = load_yaml(self.cfg["yaml_path"])
        name = data["reminders"][idx].get("name", "")
        if not messagebox.askyesno("确认删除", f"确定要删除「{name}」吗？"):
            return
        data["reminders"].pop(idx)
        save_yaml(self.cfg["yaml_path"], data)
        self._load_events()

    def _test_push(self):
        idx = self._get_selected_reminder_index()
        if idx is None:
            return
        data = load_yaml(self.cfg["yaml_path"])
        rem = data["reminders"][idx]
        name = rem.get("name", "")

        # 构造提醒内容
        parts = [f"事项：{name}"]
        if rem.get("location"):
            parts.append(f"地点：{rem['location']}")
        if rem.get("date"):
            parts.append(f"日期：{to_date_str(rem['date'])}")
        if rem.get("week"):
            parts.append(f"周次：{rem['week']}")
        if rem.get("start") and rem.get("end"):
            parts.append(f"时间：{to_date_str(rem['start'])} ~ {to_date_str(rem['end'])}")
        if rem.get("schedule"):
            schedule_lines = []
            for entry in rem["schedule"]:
                schedule_lines.append(f"  {entry.get('day', '')} {entry.get('period', '')} @{entry.get('location', '')}")
            parts.append("安排：\n" + "\n".join(schedule_lines))
        message = "\n".join(parts)

        # 桌面通知
        try:
            from plyer import notification
            notification.notify(title=f"日程提醒：{name}", message=message, timeout=10)
            desktop_ok = True
        except Exception as e:
            desktop_ok = False
            messagebox.showerror("桌面通知失败", str(e))

        # 邮件通知
        email_ok = self._send_email(f"日程提醒：{name}", message)

        if desktop_ok and email_ok:
            messagebox.showinfo("测试推送", f"桌面通知和邮件已发送\n\n{message}")
        elif desktop_ok:
            messagebox.showwarning("测试推送", f"桌面通知已发送，邮件发送失败\n\n{message}")
        elif email_ok:
            messagebox.showwarning("测试推送", f"邮件已发送，桌面通知失败\n\n{message}")

    def _send_email(self, title, content):
        import smtplib
        from email.mime.text import MIMEText
        try:
            msg = MIMEText(content, "plain", "utf-8")
            msg["From"] = self.cfg["sender_email"]
            msg["To"] = self.cfg["receiver_email"]
            msg["Subject"] = title
            with smtplib.SMTP_SSL(self.cfg["smtp_server"], int(self.cfg["smtp_port"])) as server:
                server.login(self.cfg["sender_email"], self.cfg["sender_password"])
                server.sendmail(self.cfg["sender_email"], self.cfg["receiver_email"], msg.as_string())
            return True
        except Exception as e:
            messagebox.showerror("邮件发送失败", str(e))
            return False

    # ---------- 设置页 ----------

    def _build_settings_tab(self):
        frame = ttk.LabelFrame(self.frame_settings, text="配置", padding=12)
        frame.pack(fill="x", padx=12, pady=12)

        fields = [
            ("YAML 文件路径", "yaml_path", True),
            ("SMTP 服务器", "smtp_server", False),
            ("SMTP 端口", "smtp_port", False),
            ("发件邮箱地址", "sender_email", False),
            ("SMTP 授权码", "sender_password", False),
            ("收件邮箱地址", "receiver_email", False),
        ]
        self.setting_vars = {}
        for i, (label, key, browse) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=4)
            var = tk.StringVar(value=str(self.cfg.get(key, "")))
            self.setting_vars[key] = var
            entry = ttk.Entry(frame, textvariable=var, width=52, show="*" if "password" in key else "")
            entry.grid(row=i, column=1, sticky="w", pady=4)
            if browse:
                ttk.Button(frame, text="浏览", width=6,
                           command=lambda v=var: self._browse_yaml(v)).grid(row=i, column=2, padx=(6, 0), pady=4)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(fields), column=0, columnspan=3, pady=(12, 0))
        ttk.Button(btn_frame, text="保存设置", command=self._save_settings).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="测试邮件", command=self._test_email).pack(side="left", padx=4)

    def _browse_yaml(self, var):
        path = filedialog.askopenfilename(
            title="选择 YAML 文件",
            filetypes=[("YAML 文件", "*.yaml;*.yml"), ("所有文件", "*.*")]
        )
        if path:
            var.set(path)

    def _save_settings(self):
        for key, var in self.setting_vars.items():
            val = var.get().strip()
            if key == "smtp_port":
                try:
                    val = int(val)
                except ValueError:
                    messagebox.showerror("错误", "SMTP 端口必须是数字")
                    return
            self.cfg[key] = val
        save_config(self.cfg)
        messagebox.showinfo("成功", "设置已保存")
        self._load_events()

    def _test_email(self):
        import smtplib
        from email.mime.text import MIMEText
        try:
            msg = MIMEText("这是一封测试邮件，确认邮箱推送功能正常工作。", "plain", "utf-8")
            msg["From"] = self.setting_vars["sender_email"].get()
            msg["To"] = self.setting_vars["receiver_email"].get()
            msg["Subject"] = "日程提醒测试"

            with smtplib.SMTP_SSL(
                self.setting_vars["smtp_server"].get(),
                int(self.setting_vars["smtp_port"].get())
            ) as server:
                server.login(
                    self.setting_vars["sender_email"].get(),
                    self.setting_vars["sender_password"].get()
                )
                server.sendmail(
                    self.setting_vars["sender_email"].get(),
                    self.setting_vars["receiver_email"].get(),
                    msg.as_string()
                )
            messagebox.showinfo("成功", "测试邮件已发送，请检查收件箱")
        except Exception as e:
            messagebox.showerror("发送失败", str(e))

    def run(self):
        self.root.mainloop()


# ============ 事件编辑对话框 ============

class EventDialog:
    def __init__(self, parent, title, reminder=None, callback=None):
        self.callback = callback
        self.reminder = reminder or {}
        self.result = None

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry("480x420")
        self.win.resizable(False, False)
        self.win.grab_set()

        self._build()
        if reminder:
            self._fill(reminder)

    def _build(self):
        frame = ttk.LabelFrame(self.win, text="事件信息", padding=10)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        fields = [
            ("事项名称", "name"),
            ("类型（exam/class/training/other）", "type"),
            ("地点", "location"),
            ("周次（如 第13周）", "week"),
            ("日期（YYYY-MM-DD）", "date"),
            ("时段（morning/afternoon/evening）", "time"),
            ("开始日期（YYYY-MM-DD）", "start"),
            ("结束日期（YYYY-MM-DD）", "end"),
        ]
        self.vars = {}
        for i, (label, key) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=3)
            var = tk.StringVar()
            self.vars[key] = var
            ttk.Entry(frame, textvariable=var, width=36).grid(row=i, column=1, sticky="w", pady=3)

        # schedule 区域
        ttk.Label(frame, text="每日安排（JSON格式）").grid(row=len(fields), column=0, sticky="ne", padx=(0, 8), pady=3)
        self.schedule_text = tk.Text(frame, width=36, height=4, font=("Consolas", 9))
        self.schedule_text.grid(row=len(fields), column=1, sticky="w", pady=3)
        ttk.Label(frame, text='例: [{"day":"周二","period":"3-4","location":"新安215"}]',
                  font=("", 8)).grid(row=len(fields) + 1, column=1, sticky="w")

        btn_frame = ttk.Frame(self.win)
        btn_frame.pack(pady=(0, 10))
        ttk.Button(btn_frame, text="确定", command=self._on_ok).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="取消", command=self.win.destroy).pack(side="left", padx=8)

    def _fill(self, rem):
        for key, var in self.vars.items():
            val = rem.get(key, "")
            if isinstance(val, date):
                val = val.strftime("%Y-%m-%d")
            var.set(str(val))
        if "schedule" in rem:
            self.schedule_text.insert("1.0", json.dumps(rem["schedule"], ensure_ascii=False))

    def _on_ok(self):
        rem = {}
        for key, var in self.vars.items():
            val = var.get().strip()
            if val:
                rem[key] = val
        if "name" not in rem:
            messagebox.showwarning("提示", "事项名称不能为空")
            return
        # 类型校验
        valid_types = ("exam", "class", "training", "other")
        if rem.get("type") and rem["type"] not in valid_types:
            messagebox.showwarning("提示", f"类型只能是：{', '.join(valid_types)}")
            return
        # schedule
        sched_str = self.schedule_text.get("1.0", "end").strip()
        if sched_str:
            try:
                rem["schedule"] = json.loads(sched_str)
            except json.JSONDecodeError:
                messagebox.showerror("错误", "每日安排的 JSON 格式不正确")
                return
        if self.callback:
            self.callback(rem)
        self.win.destroy()


if __name__ == "__main__":
    app = ReminderApp()
    app.run()
