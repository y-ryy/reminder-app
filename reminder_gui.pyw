"""
日程提醒工具 - 图形化界面
功能：查看/管理日程事件，修改配置（YAML路径、邮箱设置），AI 智能添加日程
"""

import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date, timedelta
import yaml
import threading

# ============ 配置文件路径 ============

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_history.json")

# AI 服务商配置
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


# ============ 对话历史 ============

MAX_HISTORY = 100


def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"history": []}


def save_history(data):
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
    # 超过上限删除最早的
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


# ============ GUI ============

class ReminderApp:
    def __init__(self):
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.title("日程提醒工具")
        self.root.geometry("860x680")
        self.root.resizable(True, True)
        self.ai_loading = False

        self._build_ui()
        self._load_events()
        self._load_chat_history()

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)

        # ---- 事件列表页 ----
        self.frame_events = ttk.Frame(notebook)
        notebook.add(self.frame_events, text="事件列表")
        self._build_events_tab()

        # ---- AI 助手页 ----
        self.frame_ai = ttk.Frame(notebook)
        notebook.add(self.frame_ai, text="AI 助手")
        self._build_ai_tab()

        # ---- 设置页 ----
        self.frame_settings = ttk.Frame(notebook)
        notebook.add(self.frame_settings, text="设置")
        self._build_settings_tab()

    # ---------- AI 助手 ----------

    def _build_ai_tab(self):
        # 对话历史
        history_frame = ttk.LabelFrame(self.frame_ai, text="对话历史", padding=6)
        history_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.chat_text = tk.Text(history_frame, height=15, wrap="word", state="disabled",
                                 font=("微软雅黑", 9))
        chat_scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=chat_scrollbar.set)
        self.chat_text.pack(side="left", fill="both", expand=True)
        chat_scrollbar.pack(side="left", fill="y")

        # 配置标签样式
        self.chat_text.tag_configure("user", foreground="#0066cc")
        self.chat_text.tag_configure("assistant", foreground="#006600")
        self.chat_text.tag_configure("error", foreground="#cc0000")
        self.chat_text.tag_configure("time", foreground="#888888", font=("微软雅黑", 8))

        # 清空历史按钮
        btn_frame = ttk.Frame(history_frame)
        btn_frame.pack(side="bottom", anchor="e", pady=(4, 0))
        ttk.Button(btn_frame, text="清空历史", command=self._clear_chat_history).pack(side="right")

        # 输入区域
        input_frame = ttk.Frame(self.frame_ai)
        input_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.ai_input = tk.Text(input_frame, height=3, wrap="word", font=("微软雅黑", 9))
        self.ai_input.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.ai_input.bind("<Return>", self._on_ai_enter)
        self.ai_input.bind("<Shift-Return>", lambda e: None)  # Shift+Enter 换行

        self.btn_send = ttk.Button(input_frame, text="发送", command=self._send_ai_message)
        self.btn_send.pack(side="right")

    def _on_ai_enter(self, event):
        # Enter 发送，Shift+Enter 换行
        if not event.state & 0x1:  # 没有按 Shift
            self._send_ai_message()
            return "break"  # 阻止默认换行

    def _load_chat_history(self):
        data = load_history()
        self.chat_text.config(state="normal")
        self.chat_text.delete("1.0", "end")
        for entry in data["history"]:
            time_str = entry["time"].split(" ")[1][:5]  # 只显示时:分
            role = entry["role"]
            content = entry["content"]
            if role == "user":
                self.chat_text.insert("end", f"[{time_str}] 你: ", "time")
                self.chat_text.insert("end", f"{content}\n", "user")
            else:
                self.chat_text.insert("end", f"[{time_str}] AI: ", "time")
                tag = "error" if "失败" in content or "错误" in content else "assistant"
                self.chat_text.insert("end", f"{content}\n", tag)
        self.chat_text.config(state="disabled")
        self.chat_text.see("end")

    def _clear_chat_history(self):
        if not messagebox.askyesno("确认", "确定要清空所有对话历史吗？"):
            return
        clear_history()
        self._load_chat_history()

    def _append_chat(self, role, content, tag="assistant"):
        time_str = datetime.now().strftime("%H:%M")
        self.chat_text.config(state="normal")
        if role == "user":
            self.chat_text.insert("end", f"[{time_str}] 你: ", "time")
            self.chat_text.insert("end", f"{content}\n", "user")
        else:
            self.chat_text.insert("end", f"[{time_str}] AI: ", "time")
            self.chat_text.insert("end", f"{content}\n", tag)
        self.chat_text.config(state="disabled")
        self.chat_text.see("end")

    def _send_ai_message(self):
        if self.ai_loading:
            return

        user_input = self.ai_input.get("1.0", "end").strip()
        if not user_input:
            return

        # 检查 API Key
        if not self.cfg.get("ai_api_key"):
            messagebox.showwarning("提示", "请先在设置中配置 AI API Key")
            return

        # 清空输入框
        self.ai_input.delete("1.0", "end")

        # 显示用户消息
        self._append_chat("user", user_input)
        add_history("user", user_input)

        # 显示加载状态
        self.ai_loading = True
        self.btn_send.config(state="disabled")
        self.ai_input.insert("1.0", "AI 思考中...")
        self.ai_input.config(state="disabled")

        # 在新线程调用 API
        threading.Thread(target=self._call_ai_api, args=(user_input,), daemon=True).start()

    def _call_ai_api(self, user_input):
        import requests

        provider_id = self.cfg.get("ai_provider", "zhipu")
        provider = AI_PROVIDERS.get(provider_id)
        if not provider:
            self.root.after(0, self._ai_error, "未知的 AI 服务商")
            return

        api_key = self.cfg["ai_api_key"]
        model = self.cfg.get("ai_model", provider["default_model"])
        base_url = provider["base_url"]

        today = date.today()
        today_str = today.strftime("%Y-%m-%d")
        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        today_weekday = weekday_names[today.weekday()]
        today_weekday_num = today.weekday()
        system_prompt = f"""你是日程解析助手。将用户的自然语言输入解析为 JSON。

当前日期：{today_str}（{today_weekday}，weekday={today_weekday_num}）

日期计算规则：
- "下周五" 指的是下周的周五，不是本周
- "下周" 是指从下周一到下周日
- "大后天" 是今天+3天，"后天" 是今天+2天，"明天" 是今天+1天
- weekday: 0=周一, 1=周二, 2=周三, 3=周四, 4=周五, 5=周六, 6=周日

重要：计算星期几的方法
给定一个日期，用 (日期 - 当前日期) % 7 + 当前weekday 来计算
例如：今天是2026-05-08（weekday=4），5月10号是(10-8)%7+4=6=周日

输出格式（只输出 JSON，不要其他内容）：

单日事件：
{{
  "name": "事项名称",
  "type": "exam/class/training/other",
  "date": "YYYY-MM-DD",
  "location": "地点"
}}

多日周期事件（如每周六的实验课）：
{{
  "name": "事项名称",
  "type": "training/class/other",
  "start": "YYYY-MM-DD",
  "end": "YYYY-MM-DD",
  "location": "地点",
  "schedule": [
    {{"day": "周六", "period": "全天", "location": "地点"}}
  ]
}}

注意：
- 只包含用户明确提到的字段，没提到的不要包含
- 如果用户没指定类型，根据语境推断（考试→exam，上课→class，实训→training）
- 如果用户给出多个日期，先计算每个日期是星期几
- 如果都是同一天（如都是周日），则只生成一个 schedule 条目
- schedule 只需包含不重复的星期几
- schedule 中的 day 用中文（周一~周日），period 用 1-4/5-8/evening/全天
- 只输出 JSON，不要有其他文字"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            "temperature": 0.1
        }

        try:
            resp = requests.post(base_url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()

            # 提取 AI 回复
            ai_content = result["choices"][0]["message"]["content"].strip()

            # 解析 JSON
            try:
                # 尝试提取 JSON（可能被 markdown 包裹）
                if "```" in ai_content:
                    json_str = ai_content.split("```")[1]
                    if json_str.startswith("json"):
                        json_str = json_str[4:]
                else:
                    json_str = ai_content

                event_data = json.loads(json_str.strip())

                # 确保有 name 字段
                if "name" not in event_data:
                    self.root.after(0, self._ai_error, "AI 返回的数据缺少事项名称")
                    return

                # 后处理：修正日期格式
                for date_field in ["date", "start", "end"]:
                    if date_field in event_data:
                        try:
                            d = datetime.strptime(str(event_data[date_field]), "%Y-%m-%d")
                            event_data[date_field] = d.strftime("%Y-%m-%d")
                        except ValueError:
                            pass

                # 后处理：修正 schedule 中的 day 和去重
                if "schedule" in event_data and "start" in event_data:
                    try:
                        start_date = datetime.strptime(event_data["start"], "%Y-%m-%d").date()
                        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                        seen = set()
                        unique_schedule = []
                        for entry in event_data["schedule"]:
                            # 根据 start 日期计算正确的星期几
                            entry["day"] = weekday_names[start_date.weekday()]
                            key = (entry.get("day"), entry.get("period"))
                            if key not in seen:
                                seen.add(key)
                                unique_schedule.append(entry)
                        event_data["schedule"] = unique_schedule
                    except ValueError:
                        pass

                # 转换日期格式并过滤空字段
                cleaned_data = {}
                for key, val in event_data.items():
                    if val is None or val == "":
                        continue
                    if key in ["date", "start", "end"]:
                        cleaned_data[key] = str(val)
                    else:
                        cleaned_data[key] = val
                event_data = cleaned_data

                self.root.after(0, self._ai_success, user_input, event_data)

            except json.JSONDecodeError:
                self.root.after(0, self._ai_error, f"AI 返回格式错误：\n{ai_content}")

        except requests.exceptions.Timeout:
            self.root.after(0, self._ai_error, "请求超时，请检查网络后重试")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                self.root.after(0, self._ai_error, "API Key 无效，请检查设置")
            elif e.response.status_code == 429:
                self.root.after(0, self._ai_error, "API 余额不足或请求过于频繁")
            else:
                self.root.after(0, self._ai_error, f"请求失败：{e}")
        except Exception as e:
            self.root.after(0, self._ai_error, f"发生错误：{e}")

    def _ai_success(self, user_input, event_data):
        self._reset_ai_input()
        self._append_chat("assistant", f"已解析事件「{event_data.get('name', '')}」，请确认")
        add_history("assistant", f"已创建事件「{event_data.get('name', '')}」", event=event_data)

        # 弹出编辑框让用户确认
        EventDialog(self.root, "AI 解析结果（请确认或修改）", reminder=event_data,
                    callback=self._save_new_event)

    def _ai_error(self, error_msg):
        self._reset_ai_input()
        self._append_chat("assistant", f"失败：{error_msg}", tag="error")
        add_history("assistant", f"失败：{error_msg}")

    def _reset_ai_input(self):
        self.ai_loading = False
        self.btn_send.config(state="normal")
        self.ai_input.config(state="normal")
        self.ai_input.delete("1.0", "end")

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

        def get_sort_key(rem):
            """获取排序用的日期，没有日期的排最后"""
            if "date" in rem:
                try:
                    return datetime.strptime(str(rem["date"]), "%Y-%m-%d").date()
                except ValueError:
                    pass
            if "start" in rem:
                try:
                    return datetime.strptime(str(rem["start"]), "%Y-%m-%d").date()
                except ValueError:
                    pass
            if "week" in rem:
                # 按周次排序
                try:
                    week_num = int(rem["week"].replace("第", "").replace("周", ""))
                    return SEMESTER_START + timedelta(weeks=week_num - 1)
                except ValueError:
                    pass
            return date.max  # 没有日期的排最后

        # 按日期排序
        reminders = data.get("reminders", [])
        sorted_reminders = sorted(enumerate(reminders), key=lambda x: get_sort_key(x[1]))

        for idx, rem in sorted_reminders:
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
        # 创建可滚动的画布
        canvas = tk.Canvas(self.frame_settings)
        scrollbar = ttk.Scrollbar(self.frame_settings, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        scrollbar.pack(side="right", fill="y")

        # 邮件配置
        mail_frame = ttk.LabelFrame(scrollable_frame, text="邮件配置", padding=12)
        mail_frame.pack(fill="x", padx=0, pady=(0, 12))

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
            ttk.Label(mail_frame, text=label).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=4)
            var = tk.StringVar(value=str(self.cfg.get(key, "")))
            self.setting_vars[key] = var
            entry = ttk.Entry(mail_frame, textvariable=var, width=52, show="*" if "password" in key else "")
            entry.grid(row=i, column=1, sticky="w", pady=4)
            if browse:
                ttk.Button(mail_frame, text="浏览", width=6,
                           command=lambda v=var: self._browse_yaml(v)).grid(row=i, column=2, padx=(6, 0), pady=4)

        mail_btn_frame = ttk.Frame(mail_frame)
        mail_btn_frame.grid(row=len(fields), column=0, columnspan=3, pady=(12, 0))
        ttk.Button(mail_btn_frame, text="保存设置", command=self._save_settings).pack(side="left", padx=4)
        ttk.Button(mail_btn_frame, text="测试邮件", command=self._test_email).pack(side="left", padx=4)

        # AI 配置
        ai_frame = ttk.LabelFrame(scrollable_frame, text="AI 配置", padding=12)
        ai_frame.pack(fill="x", padx=0, pady=(0, 12))

        # AI 服务商
        ttk.Label(ai_frame, text="AI 服务商").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        self.ai_provider_var = tk.StringVar(value=self.cfg.get("ai_provider", "zhipu"))
        provider_names = [v["name"] for v in AI_PROVIDERS.values()]
        provider_ids = list(AI_PROVIDERS.keys())
        self.provider_combo = ttk.Combobox(ai_frame, textvariable=self.ai_provider_var,
                                           values=provider_names, state="readonly", width=20)
        self.provider_combo.grid(row=0, column=1, sticky="w", pady=4)
        self.provider_combo.current(provider_ids.index(self.cfg.get("ai_provider", "zhipu")))
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)

        # AI 模型
        ttk.Label(ai_frame, text="AI 模型").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        self.ai_model_var = tk.StringVar(value=self.cfg.get("ai_model", "glm-4-flash"))
        self.model_combo = ttk.Combobox(ai_frame, textvariable=self.ai_model_var,
                                        state="readonly", width=30)
        self.model_combo.grid(row=1, column=1, sticky="w", pady=4)
        self._update_model_list()

        # API Key
        ttk.Label(ai_frame, text="API Key").grid(row=2, column=0, sticky="e", padx=(0, 8), pady=4)
        self.ai_key_var = tk.StringVar(value=self.cfg.get("ai_api_key", ""))
        ttk.Entry(ai_frame, textvariable=self.ai_key_var, width=52, show="*").grid(
            row=2, column=1, sticky="w", pady=4)

        ai_btn_frame = ttk.Frame(ai_frame)
        ai_btn_frame.grid(row=3, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(ai_btn_frame, text="保存 AI 设置", command=self._save_ai_settings).pack(side="left", padx=4)

    def _on_provider_change(self, event):
        self._update_model_list()

    def _update_model_list(self):
        provider_names = [v["name"] for v in AI_PROVIDERS.values()]
        provider_ids = list(AI_PROVIDERS.keys())
        idx = self.provider_combo.current()
        if idx < 0:
            idx = 0
        provider_id = provider_ids[idx]
        provider = AI_PROVIDERS[provider_id]
        model_names = [m["name"] for m in provider["models"]]
        self.model_combo["values"] = model_names
        # 设置当前模型
        current_model = self.cfg.get("ai_model", provider["default_model"])
        for i, m in enumerate(provider["models"]):
            if m["id"] == current_model:
                self.model_combo.current(i)
                return
        self.model_combo.current(0)

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

    def _save_ai_settings(self):
        provider_names = [v["name"] for v in AI_PROVIDERS.values()]
        provider_ids = list(AI_PROVIDERS.keys())
        idx = self.provider_combo.current()
        if idx < 0:
            idx = 0
        provider_id = provider_ids[idx]
        provider = AI_PROVIDERS[provider_id]

        model_idx = self.model_combo.current()
        if model_idx < 0:
            model_idx = 0
        model_id = provider["models"][model_idx]["id"]

        self.cfg["ai_provider"] = provider_id
        self.cfg["ai_model"] = model_id
        self.cfg["ai_api_key"] = self.ai_key_var.get().strip()

        save_config(self.cfg)
        messagebox.showinfo("成功", "AI 设置已保存")

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
        self.schedule_list = []  # 存储 schedule 数据

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry("520x580")
        self.win.resizable(False, False)
        self.win.grab_set()

        self._build()
        if reminder:
            self._fill(reminder)

    def _build(self):
        # 基本信息区域
        info_frame = ttk.LabelFrame(self.win, text="事件信息", padding=10)
        info_frame.pack(fill="x", padx=10, pady=(10, 5))

        fields = [
            ("事项名称 *", "name"),
            ("类型", "type"),
            ("地点", "location"),
            ("周次", "week"),
            ("日期", "date"),
            ("时段", "time"),
            ("开始日期", "start"),
            ("结束日期", "end"),
        ]
        self.vars = {}
        for i, (label, key) in enumerate(fields):
            row, col = divmod(i, 2)
            ttk.Label(info_frame, text=label).grid(row=row, column=col * 2, sticky="e", padx=(0, 4), pady=3)
            var = tk.StringVar()
            self.vars[key] = var
            width = 18 if col == 1 else 16
            ttk.Entry(info_frame, textvariable=var, width=width).grid(
                row=row, column=col * 2 + 1, sticky="w", padx=(0, 12), pady=3)

        # 类型提示
        ttk.Label(info_frame, text="类型: exam/class/training/other", font=("", 8),
                  foreground="gray").grid(row=4, column=0, columnspan=4, sticky="w")

        # 每日安排区域
        sched_frame = ttk.LabelFrame(self.win, text="每日安排（用于多日事件，如实训、课程）", padding=10)
        sched_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 已添加的安排列表
        cols = ("day", "period", "location")
        self.sched_tree = ttk.Treeview(sched_frame, columns=cols, show="headings", height=5)
        self.sched_tree.heading("day", text="星期")
        self.sched_tree.heading("period", text="时段")
        self.sched_tree.heading("location", text="地点")
        self.sched_tree.column("day", width=80)
        self.sched_tree.column("period", width=100)
        self.sched_tree.column("location", width=200)
        self.sched_tree.pack(fill="both", expand=True, pady=(0, 8))

        # 添加安排的输入区域
        add_frame = ttk.Frame(sched_frame)
        add_frame.pack(fill="x")

        ttk.Label(add_frame, text="星期").pack(side="left", padx=(0, 4))
        self.day_var = tk.StringVar(value="周一")
        day_combo = ttk.Combobox(add_frame, textvariable=self.day_var, width=6,
                                 values=["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
                                 state="readonly")
        day_combo.pack(side="left", padx=(0, 8))

        ttk.Label(add_frame, text="时段").pack(side="left", padx=(0, 4))
        self.period_var = tk.StringVar(value="1-4")
        period_combo = ttk.Combobox(add_frame, textvariable=self.period_var, width=8,
                                    values=["1-4", "5-8", "evening", "全天"],
                                    state="readonly")
        period_combo.pack(side="left", padx=(0, 8))

        ttk.Label(add_frame, text="地点").pack(side="left", padx=(0, 4))
        self.sched_loc_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.sched_loc_var, width=14).pack(side="left", padx=(0, 8))

        ttk.Button(add_frame, text="添加", width=6, command=self._add_schedule).pack(side="left")
        ttk.Button(add_frame, text="删除选中", width=8, command=self._del_schedule).pack(side="left", padx=(4, 0))

        # 底部按钮
        btn_frame = ttk.Frame(self.win)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="确定", command=self._on_ok).pack(side="left", padx=8)
        ttk.Button(btn_frame, text="取消", command=self.win.destroy).pack(side="left", padx=8)

    def _add_schedule(self):
        day = self.day_var.get()
        period = self.period_var.get()
        location = self.sched_loc_var.get().strip()

        if not location:
            messagebox.showwarning("提示", "请输入地点")
            return

        self.schedule_list.append({"day": day, "period": period, "location": location})
        self.sched_tree.insert("", "end", values=(day, period, location))
        self.sched_loc_var.set("")

    def _del_schedule(self):
        sel = self.sched_tree.selection()
        if not sel:
            return
        for item in sel:
            idx = self.sched_tree.index(item)
            self.schedule_list.pop(idx)
            self.sched_tree.delete(item)

    def _fill(self, rem):
        for key, var in self.vars.items():
            val = rem.get(key, "")
            if isinstance(val, date):
                val = val.strftime("%Y-%m-%d")
            var.set(str(val))
        if "schedule" in rem:
            self.schedule_list = rem["schedule"]
            for entry in self.schedule_list:
                self.sched_tree.insert("", "end", values=(
                    entry.get("day", ""),
                    entry.get("period", ""),
                    entry.get("location", "")
                ))

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
        if self.schedule_list:
            rem["schedule"] = self.schedule_list
        if self.callback:
            self.callback(rem)
        self.win.destroy()


if __name__ == "__main__":
    app = ReminderApp()
    app.run()
