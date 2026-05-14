"""
日程提醒工具 - 图形化界面
功能：查看/管理日程事件，修改配置（YAML路径、邮箱设置），AI 智能添加日程
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, date, timedelta
import threading

# 将 src/ 加入模块搜索路径
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from config import load_config, save_config, AI_PROVIDERS, get_semester_start
from storage import load_yaml, save_yaml, to_date_str, load_history, add_history, clear_history
from storage import load_notification_history, export_to_md
from notifications import send_email, send_desktop
from ai_service import call_ai_api
from reminder_engine import (
    generate_reminders, auto_complete_timeout, regenerate_reminders,
    send_startup_reminder, start_reminder_checker,
)
from event_dialog import EventDialog


class ReminderApp:
    def __init__(self):
        # 设置任务栏图标ID（必须在窗口创建前）
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("reminder.tool.v1")
        except Exception:
            pass

        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.title("日程提醒工具")
        self.root.geometry("860x680")
        self.root.resizable(True, True)
        self.ai_loading = False
        self.tray_icon = None

        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "图片2.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        self._apply_global_font()
        self._build_ui()
        self._load_events()
        self._load_chat_history()
        start_reminder_checker(self.cfg)
        send_startup_reminder(self.cfg)
        self._setup_tray()

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=6, pady=6)

        self.frame_events = ttk.Frame(notebook)
        notebook.add(self.frame_events, text="事件列表")
        self._build_events_tab()

        self.frame_ai = ttk.Frame(notebook)
        notebook.add(self.frame_ai, text="AI 助手")
        self._build_ai_tab()

        self.frame_settings = ttk.Frame(notebook)
        notebook.add(self.frame_settings, text="设置")
        self._build_settings_tab()

        self.frame_notify_history = ttk.Frame(notebook)
        notebook.add(self.frame_notify_history, text="通知历史")
        self._build_notify_history_tab()

    # ==================== 字体管理 ====================

    def _get_font(self, size=None):
        family = self.cfg.get("font_family", "微软雅黑")
        if size is None:
            size = self.cfg.get("font_size", 14)
        return (family, size)

    def _apply_global_font(self):
        """将字体设置应用到所有 ttk 控件"""
        family, size = self._get_font()
        style = ttk.Style()
        style.configure(".", font=(family, size))
        style.configure("Treeview", font=(family, size), rowheight=int(size * 2))
        style.configure("Treeview.Heading", font=(family, size))
        style.configure("TLabel", font=(family, size))
        style.configure("TButton", font=(family, size))
        style.configure("TCheckbutton", font=(family, size))
        style.configure("TLabelframe.Label", font=(family, size))
        style.configure("TCombobox", font=(family, size))
        style.configure("TSpinbox", font=(family, size))

    # ==================== 系统托盘 ====================

    def _setup_tray(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self.tray_icon = self._create_tray_icon()
        if self.tray_icon:
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _create_tray_icon(self):
        """创建托盘图标（启动时创建一次）"""
        try:
            import pystray
            from PIL import Image

            png_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "tray_icon.png")
            ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "图片2.ico")
            if os.path.exists(png_path):
                image = Image.open(png_path)
            elif os.path.exists(ico_path):
                image = Image.open(ico_path).convert("RGBA").resize((64, 64), Image.LANCZOS)
            else:
                image = Image.new("RGB", (64, 64), "#4a90d9")

            menu = pystray.Menu(
                pystray.MenuItem("显示窗口", self._restore_from_tray, default=True),
                pystray.MenuItem("重启", self._restart_app),
                pystray.MenuItem("退出", self._exit_app)
            )
            return pystray.Icon("reminder", image, "日程提醒工具", menu)
        except Exception as e:
            print(f"托盘初始化失败: {e}")
            return None

    def _on_window_close(self):
        if self.cfg.get("minimize_to_tray", False):
            self._minimize_to_tray()
        else:
            self._exit_app()

    def _minimize_to_tray(self):
        self.root.withdraw()

    def _restore_from_tray(self, icon=None, item=None):
        self.root.after(0, self._do_restore)

    def _do_restore(self):
        self.root.deiconify()
        self.root.lift()

    def _exit_app(self, icon=None, item=None):
        if icon:
            icon.stop()
        elif self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def _restart_app(self, icon=None, item=None):
        if icon:
            icon.stop()
        elif self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self._do_restart)

    def _do_restart(self):
        import subprocess
        script = os.path.abspath(sys.argv[0])
        self.root.destroy()
        subprocess.Popen([sys.executable, script])

    # ==================== AI 助手 ====================

    def _build_ai_tab(self):
        # 对话历史（顶部，可扩展）
        history_frame = ttk.LabelFrame(self.frame_ai, text="对话历史", padding=6)
        history_frame.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        self.chat_text = tk.Text(history_frame, height=15, wrap="word", state="disabled",
                                 font=self._get_font())
        chat_scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.chat_text.yview)
        self.chat_text.configure(yscrollcommand=chat_scrollbar.set)
        self.chat_text.pack(side="left", fill="both", expand=True)
        chat_scrollbar.pack(side="left", fill="y")

        self.chat_text.tag_configure("user", foreground="#0066cc")
        self.chat_text.tag_configure("assistant", foreground="#006600")
        self.chat_text.tag_configure("error", foreground="#cc0000")
        self.chat_text.tag_configure("time", foreground="#888888", font=self._get_font(12))

        # 清空历史按钮
        btn_frame = ttk.Frame(self.frame_ai)
        btn_frame.pack(fill="x", padx=8, pady=(0, 4))
        ttk.Button(btn_frame, text="清空历史", command=self._clear_chat_history).pack(side="right")

        # 输入框 + 发送按钮（底部）
        input_frame = ttk.Frame(self.frame_ai)
        input_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.ai_input = tk.Text(input_frame, height=3, wrap="word", font=self._get_font())
        self.ai_input.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.ai_input.bind("<Return>", self._on_ai_enter)
        self.ai_input.bind("<Shift-Return>", lambda e: None)

        self.btn_send = ttk.Button(input_frame, text="发送", command=self._send_ai_message)
        self.btn_send.pack(side="right", fill="y")

    def _on_ai_enter(self, event):
        if not event.state & 0x1:
            self._send_ai_message()
            return "break"

    def _load_chat_history(self):
        data = load_history()
        self.chat_text.config(state="normal")
        self.chat_text.delete("1.0", "end")
        for entry in data["history"]:
            time_str = entry["time"].split(" ")[1][:5]
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

        if not self.cfg.get("ai_api_key"):
            messagebox.showwarning("提示", "请先在设置中配置 AI API Key")
            return

        self.ai_input.delete("1.0", "end")
        self._append_chat("user", user_input)
        add_history("user", user_input)

        self.ai_loading = True
        self.btn_send.config(state="disabled")
        self.ai_input.insert("1.0", "AI 思考中...")
        self.ai_input.config(state="disabled")

        threading.Thread(target=self._call_ai_api, args=(user_input,), daemon=True).start()

    def _call_ai_api(self, user_input):
        event_data, error_msg = call_ai_api(self.cfg, user_input)
        if error_msg:
            self.root.after(0, self._ai_error, error_msg)
        else:
            self.root.after(0, self._ai_success, user_input, event_data)

    def _ai_success(self, user_input, event_data):
        self._reset_ai_input()
        self._append_chat("assistant", f"已解析事件「{event_data.get('name', '')}」，请确认")
        add_history("assistant", f"已创建事件「{event_data.get('name', '')}」", event=event_data)
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

    # ==================== 事件列表 ====================

    def _build_events_tab(self):
        self.checked = "☑"
        self.unchecked = "☐"

        # 搜索/筛选栏
        filter_frame = ttk.Frame(self.frame_events)
        filter_frame.pack(fill="x", padx=6, pady=(6, 0))

        ttk.Label(filter_frame, text="搜索").pack(side="left", padx=(0, 4))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side="left", padx=(0, 8))
        search_entry.bind("<Return>", lambda e: self._load_events())

        ttk.Label(filter_frame, text="类型").pack(side="left", padx=(0, 4))
        self.filter_type_var = tk.StringVar(value="全部")
        type_combo = ttk.Combobox(filter_frame, textvariable=self.filter_type_var,
                                  values=["全部", "exam", "class", "training", "other"],
                                  state="readonly", width=10)
        type_combo.pack(side="left", padx=(0, 8))
        type_combo.bind("<<ComboboxSelected>>", lambda e: self._load_events())

        ttk.Button(filter_frame, text="搜索", command=self._load_events, width=6).pack(side="left", padx=(0, 4))
        ttk.Button(filter_frame, text="重置", command=self._reset_filter, width=6).pack(side="left")

        cols = ("status", "type", "date", "week", "location")
        self.tree = ttk.Treeview(self.frame_events, columns=cols, show="tree headings", height=15)
        self.tree.heading("#0", text="事项名称")
        self.tree.heading("status", text="状态")
        self.tree.heading("type", text="类型")
        self.tree.heading("date", text="日期")
        self.tree.heading("week", text="周次")
        self.tree.heading("location", text="地点")
        self.tree.column("#0", width=200)
        self.tree.column("status", width=60, anchor="center")
        self.tree.column("type", width=60, anchor="center")
        self.tree.column("date", width=110)
        self.tree.column("week", width=100)
        self.tree.column("location", width=200)

        scrollbar = ttk.Scrollbar(self.frame_events, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        scrollbar.pack(side="left", fill="y", pady=6, padx=(0, 6))

        self.tree.tag_configure("completed", foreground="gray")
        self.tree.bind("<Button-1>", self._on_tree_click)

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
        self._rem_index_map = {}
        try:
            data = load_yaml(self.cfg["yaml_path"])
        except FileNotFoundError:
            messagebox.showwarning("提示", f"YAML 文件不存在：\n{self.cfg['yaml_path']}")
            return
        except Exception as e:
            messagebox.showerror("错误", f"读取 YAML 失败：{e}")
            return

        auto_complete_timeout(self.cfg, data)
        regenerate_reminders(self.cfg, data)

        # 搜索/筛选
        search_text = self.search_var.get().strip().lower()
        filter_type = self.filter_type_var.get()

        WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday_map = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}
        type_labels = {"exam": "考试", "class": "上课", "training": "实训", "other": "其他"}
        period_labels = {"1-4": "1~4节", "5-8": "5~8节", "evening": "晚课", "全天": "全天"}
        semester_start = get_semester_start(self.cfg)

        def calc_week(d):
            week_num = (d - semester_start).days // 7 + 1
            return f"第{week_num}周{WEEKDAY_NAMES[d.weekday()]}"

        def get_sort_key(rem):
            # 多日事件：按下一个待办子项日期排序
            sub_items = rem.get("sub_items", {})
            if sub_items and "start" in rem and "end" in rem:
                pending_dates = sorted(d for d, v in sub_items.items() if not v.get("completed"))
                if pending_dates:
                    try:
                        return datetime.strptime(pending_dates[0], "%Y-%m-%d").date()
                    except ValueError:
                        pass
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
                try:
                    week_num = int(rem["week"].replace("第", "").replace("周", ""))
                    return semester_start + timedelta(weeks=week_num - 1)
                except ValueError:
                    pass
            return date.max

        def get_completed_time(rem):
            completed_at = rem.get("completed_at", "")
            if completed_at:
                try:
                    return datetime.strptime(completed_at, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            return datetime.min

        reminders = data.get("reminders", [])

        # 分离：普通事件按 completed 分组，多日部分完成事件两边都显示
        pending = []
        completed = []
        partial_events = []  # (idx, rem) 多日任务且部分完成

        for idx, rem in enumerate(reminders):
            # 搜索/筛选
            if search_text and search_text not in rem.get("name", "").lower():
                continue
            if filter_type != "全部" and rem.get("type") != filter_type:
                continue

            has_schedule = "schedule" in rem and "start" in rem and "end" in rem
            sub_items = rem.get("sub_items", {})
            if has_schedule and sub_items:
                done = sum(1 for v in sub_items.values() if v.get("completed"))
                total = len(sub_items)
                if 0 < done < total:
                    partial_events.append((idx, rem))
                    continue
            if rem.get("completed"):
                completed.append((idx, rem))
            else:
                pending.append((idx, rem))

        pending_sorted = sorted(pending + partial_events, key=lambda x: get_sort_key(x[1]))
        completed_sorted = sorted(completed + partial_events, key=lambda x: get_sort_key(x[1]), reverse=True)

        # 未完成分组
        pending_parent = self.tree.insert("", "end", text=f"未完成 ({len(pending_sorted)})", open=True)
        self._rem_index_map[pending_parent] = (-1, None)

        for idx, rem in pending_sorted:
            has_schedule = "schedule" in rem and "start" in rem and "end" in rem
            sub_items = rem.get("sub_items", {})
            is_partial = has_schedule and sub_items and 0 < sum(1 for v in sub_items.values() if v.get("completed")) < len(sub_items)
            filter_sub = "pending" if is_partial else None
            self._insert_reminder(pending_parent, idx, rem, type_labels, period_labels,
                                  calc_week, weekday_map, completed=False, filter_sub=filter_sub)

        # 已完成分组
        completed_parent = self.tree.insert("", "end", text=f"已完成 ({len(completed_sorted)})", open=True)
        self._rem_index_map[completed_parent] = (-1, None)

        for idx, rem in completed_sorted:
            has_schedule = "schedule" in rem and "start" in rem and "end" in rem
            sub_items = rem.get("sub_items", {})
            is_partial = has_schedule and sub_items and 0 < sum(1 for v in sub_items.values() if v.get("completed")) < len(sub_items)
            filter_sub = "completed" if is_partial else None
            self._insert_reminder(completed_parent, idx, rem, type_labels, period_labels,
                                  calc_week, weekday_map, completed=True, filter_sub=filter_sub)

    def _insert_reminder(self, parent, idx, rem, type_labels, period_labels, calc_week, weekday_map, completed, filter_sub=None):
        name = rem.get("name", "")
        rtype = type_labels.get(rem.get("type", ""), rem.get("type", ""))
        loc = rem.get("location", "")
        status = self.checked if completed else self.unchecked
        tags = ("completed",) if completed else ()

        # 多日事件 — 子项可独立完成
        if "schedule" in rem and "start" in rem and "end" in rem:
            start = to_date_str(rem["start"])
            end = to_date_str(rem["end"])
            week = rem.get("week", "")
            sub_items = rem.get("sub_items", {})

            all_dates = []
            try:
                start_d = datetime.strptime(start, "%Y-%m-%d").date()
                end_d = datetime.strptime(end, "%Y-%m-%d").date()
            except ValueError:
                return

            for entry in rem.get("schedule", []):
                entry_wd = weekday_map.get(entry.get("day"))
                if entry_wd is not None:
                    d = start_d
                    while d <= end_d:
                        if d.weekday() == entry_wd:
                            all_dates.append((d, entry))
                        d += timedelta(days=1)

            # 按 filter_sub 过滤子项
            if filter_sub == "pending":
                filtered = [(d, e) for d, e in all_dates if not sub_items.get(str(d), {}).get("completed")]
            elif filter_sub == "completed":
                filtered = [(d, e) for d, e in all_dates if sub_items.get(str(d), {}).get("completed")]
            else:
                filtered = all_dates

            if not filtered:
                return

            done_count = sum(1 for d, _ in all_dates if sub_items.get(str(d), {}).get("completed"))
            total_count = len(all_dates)
            if filter_sub:
                parent_status = self.checked if completed else self.unchecked
                parent_tags = ("completed",) if completed else ()
            elif total_count > 0 and done_count == total_count:
                parent_status = self.checked
                parent_tags = ("completed",)
            elif done_count > 0:
                parent_status = f"[{done_count}/{total_count}]"
                parent_tags = ()
            else:
                parent_status = self.unchecked
                parent_tags = ()

            date_display = f"{start} ~ {end}"
            parent_id = self.tree.insert(parent, "end", text=name,
                                         values=(parent_status, rtype, date_display, week, loc),
                                         tags=parent_tags)
            self._rem_index_map[parent_id] = (idx, None)

            for d, entry in filtered:
                period = entry.get("period", "全天")
                entry_loc = entry.get("location", loc)
                period_label = period_labels.get(period, period)
                date_str = d.strftime("%Y-%m-%d")
                sub = sub_items.get(date_str, {})
                sub_done = sub.get("completed", False)
                sub_status = self.checked if sub_done else self.unchecked
                sub_tags = ("completed",) if sub_done else ()
                child_id = self.tree.insert(
                    parent_id, "end",
                    text=f"{entry['day']} {period_label}",
                    values=(sub_status, "", date_str, calc_week(d), entry_loc),
                    tags=sub_tags)
                self._rem_index_map[child_id] = (idx, date_str)
        else:
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
            item_id = self.tree.insert(parent, "end", text=name,
                                       values=(status, rtype, date_str, week_str, loc),
                                       tags=tags)
            self._rem_index_map[item_id] = (idx, None)

    def _reset_filter(self):
        self.search_var.set("")
        self.filter_type_var.set("全部")
        self._load_events()

    def _on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)
        if column not in ("#1", "#0"):
            return
        info = self._rem_index_map.get(item)
        if info is None:
            return
        idx, sub_date = info
        if idx < 0:
            return
        self._toggle_complete(idx, sub_date)

    @staticmethod
    def _get_all_scheduled_dates(rem):
        """获取多日事件所有应出现的日期集合"""
        weekday_map = {"周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6}
        if "schedule" not in rem or "start" not in rem or "end" not in rem:
            return set()
        try:
            start_d = datetime.strptime(to_date_str(rem["start"]), "%Y-%m-%d").date()
            end_d = datetime.strptime(to_date_str(rem["end"]), "%Y-%m-%d").date()
        except ValueError:
            return set()
        dates = set()
        for entry in rem.get("schedule", []):
            entry_wd = weekday_map.get(entry.get("day"))
            if entry_wd is not None:
                d = start_d
                while d <= end_d:
                    if d.weekday() == entry_wd:
                        dates.add(str(d))
                    d += timedelta(days=1)
        return dates

    def _toggle_complete(self, idx, sub_date=None):
        data = load_yaml(self.cfg["yaml_path"])
        rem = data["reminders"][idx]

        if sub_date:
            sub_items = rem.setdefault("sub_items", {})
            sub = sub_items.setdefault(sub_date, {})
            if sub.get("completed"):
                sub["completed"] = False
                sub.pop("completed_at", None)
            else:
                sub["completed"] = True
                sub["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 检查所有应出现的日期是否都已完成（而非仅检查已有条目）
            all_dates = self._get_all_scheduled_dates(rem)
            if all_dates:
                all_done = all(sub_items.get(d, {}).get("completed") for d in all_dates)
            else:
                all_done = all(v.get("completed") for v in sub_items.values()) if sub_items else False
            if all_done and not rem.get("completed"):
                rem["completed"] = True
                rem["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elif not all_done and rem.get("completed"):
                rem["completed"] = False
                rem.pop("completed_at", None)
        else:
            all_dates = self._get_all_scheduled_dates(rem)
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if rem.get("completed"):
                rem["completed"] = False
                rem.pop("completed_at", None)
                for sub in rem.get("sub_items", {}).values():
                    sub["completed"] = False
                    sub.pop("completed_at", None)
            else:
                rem["completed"] = True
                rem["completed_at"] = now_str
                sub_items = rem.setdefault("sub_items", {})
                for d in all_dates:
                    sub = sub_items.setdefault(d, {})
                    sub["completed"] = True
                    sub["completed_at"] = now_str

        save_yaml(self.cfg["yaml_path"], data, self.cfg)
        self._load_events()

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
        info = self._rem_index_map.get(sel[0])
        if info is None:
            messagebox.showinfo("提示", "请先选择一条事件")
            return None
        idx, sub_date = info
        if idx < 0:
            messagebox.showinfo("提示", "请先选择一条事件")
            return None
        return idx

    def _add_event(self):
        EventDialog(self.root, "添加事件", callback=self._save_new_event)

    def _save_new_event(self, rem):
        generate_reminders(rem)
        data = load_yaml(self.cfg["yaml_path"])
        data.setdefault("reminders", []).append(rem)
        save_yaml(self.cfg["yaml_path"], data, self.cfg)
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
        generate_reminders(rem)
        data = load_yaml(self.cfg["yaml_path"])
        data["reminders"][idx] = rem
        save_yaml(self.cfg["yaml_path"], data, self.cfg)
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
        save_yaml(self.cfg["yaml_path"], data, self.cfg)
        self._load_events()

    def _test_push(self):
        idx = self._get_selected_reminder_index()
        if idx is None:
            return
        data = load_yaml(self.cfg["yaml_path"])
        rem = data["reminders"][idx]
        name = rem.get("name", "")

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

        desktop_ok = False
        if self.cfg.get("enable_desktop", True):
            desktop_ok = send_desktop(f"日程提醒：{name}", message)
            if not desktop_ok:
                messagebox.showerror("桌面通知失败", "请检查 plyer 是否安装")

        email_ok = False
        if self.cfg.get("enable_email", True):
            email_ok = send_email(self.cfg, f"日程提醒：{name}", message)
            if not email_ok:
                messagebox.showerror("邮件发送失败", "请检查邮件配置")

        if desktop_ok and email_ok:
            messagebox.showinfo("测试推送", f"桌面通知和邮件已发送\n\n{message}")
        elif desktop_ok:
            messagebox.showwarning("测试推送", f"桌面通知已发送，邮件发送失败\n\n{message}")
        elif email_ok:
            messagebox.showwarning("测试推送", f"邮件已发送，桌面通知失败\n\n{message}")

    # ==================== 设置页 ====================

    def _build_settings_tab(self):
        # 可滚动画布 + 居中容器
        container = ttk.Frame(self.frame_settings)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="n")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 窗口宽度变化时居中内容
        def _on_canvas_resize(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        # 绑定鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 字体设置
        font_frame = ttk.LabelFrame(scrollable_frame, text="字体设置", padding=12)
        font_frame.pack(fill="x", padx=20, pady=(12, 12))

        ttk.Label(font_frame, text="字体").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        self.font_family_var = tk.StringVar(value=self.cfg.get("font_family", "微软雅黑"))
        font_families = ["微软雅黑", "宋体", "黑体", "Arial", "Consolas"]
        ttk.Combobox(font_frame, textvariable=self.font_family_var, values=font_families,
                     width=20).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(font_frame, text="字号").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        self.font_size_var = tk.StringVar(value=str(self.cfg.get("font_size", 14)))
        ttk.Spinbox(font_frame, textvariable=self.font_size_var, from_=8, to=36,
                    width=8).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Button(font_frame, text="保存字体设置", command=self._save_font_settings).grid(
            row=2, column=0, columnspan=2, pady=(8, 0))

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
            ("学期起始日", "semester_start", False),
            ("MD 导出路径", "export_md_path", True),
        ]
        self.setting_vars = {}
        for i, (label, key, browse) in enumerate(fields):
            ttk.Label(mail_frame, text=label).grid(row=i, column=0, sticky="e", padx=(0, 8), pady=4)
            var = tk.StringVar(value=str(self.cfg.get(key, "")))
            self.setting_vars[key] = var
            entry = ttk.Entry(mail_frame, textvariable=var, width=52, show="*" if "password" in key else "")
            entry.grid(row=i, column=1, sticky="w", pady=4)
            if browse:
                cmd = (lambda v=var, k=key: self._browse_md_export(v) if k == "export_md_path" else self._browse_yaml(v))
                ttk.Button(mail_frame, text="浏览", width=6,
                           command=cmd).grid(row=i, column=2, padx=(6, 0), pady=4)

        mail_btn_frame = ttk.Frame(mail_frame)
        mail_btn_frame.grid(row=len(fields), column=0, columnspan=3, pady=(12, 0))
        ttk.Button(mail_btn_frame, text="保存设置", command=self._save_settings).pack(side="left", padx=4)
        ttk.Button(mail_btn_frame, text="测试邮件", command=self._test_email).pack(side="left", padx=4)
        ttk.Button(mail_btn_frame, text="手动导出", command=self._manual_export).pack(side="left", padx=4)

        # 通知方式
        notify_frame = ttk.LabelFrame(scrollable_frame, text="通知方式", padding=12)
        notify_frame.pack(fill="x", padx=0, pady=(0, 12))

        self.enable_email_var = tk.BooleanVar(value=self.cfg.get("enable_email", True))
        self.enable_desktop_var = tk.BooleanVar(value=self.cfg.get("enable_desktop", True))
        self.minimize_to_tray_var = tk.BooleanVar(value=self.cfg.get("minimize_to_tray", False))

        ttk.Checkbutton(notify_frame, text="启用邮件通知", variable=self.enable_email_var).grid(
            row=0, column=0, sticky="w", pady=4)
        ttk.Checkbutton(notify_frame, text="启用桌面通知", variable=self.enable_desktop_var).grid(
            row=1, column=0, sticky="w", pady=4)
        ttk.Checkbutton(notify_frame, text="最小化到系统托盘", variable=self.minimize_to_tray_var).grid(
            row=2, column=0, sticky="w", pady=4)

        ttk.Button(notify_frame, text="保存通知设置", command=self._save_notify_settings).grid(
            row=3, column=0, pady=(8, 0))

        # AI 配置
        ai_frame = ttk.LabelFrame(scrollable_frame, text="AI 配置", padding=12)
        ai_frame.pack(fill="x", padx=0, pady=(0, 12))

        ttk.Label(ai_frame, text="AI 服务商").grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        self.ai_provider_var = tk.StringVar(value=self.cfg.get("ai_provider", "zhipu"))
        provider_names = [v["name"] for v in AI_PROVIDERS.values()]
        provider_ids = list(AI_PROVIDERS.keys())
        self.provider_combo = ttk.Combobox(ai_frame, textvariable=self.ai_provider_var,
                                           values=provider_names, state="readonly", width=20)
        self.provider_combo.grid(row=0, column=1, sticky="w", pady=4)
        self.provider_combo.current(provider_ids.index(self.cfg.get("ai_provider", "zhipu")))
        self.provider_combo.bind("<<ComboboxSelected>>", self._on_provider_change)

        ttk.Label(ai_frame, text="AI 模型").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        self.ai_model_var = tk.StringVar(value=self.cfg.get("ai_model", "glm-4-flash"))
        self.model_combo = ttk.Combobox(ai_frame, textvariable=self.ai_model_var,
                                        state="readonly", width=30)
        self.model_combo.grid(row=1, column=1, sticky="w", pady=4)
        self._update_model_list()

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

    def _browse_md_export(self, var):
        path = filedialog.askdirectory(title="选择 MD 导出目录")
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

    def _save_font_settings(self):
        self.cfg["font_family"] = self.font_family_var.get()
        try:
            self.cfg["font_size"] = int(self.font_size_var.get())
        except ValueError:
            messagebox.showerror("错误", "字号必须是数字")
            return
        save_config(self.cfg)
        messagebox.showinfo("成功", "字体设置已保存，重启程序后生效")

    def _save_notify_settings(self):
        self.cfg["enable_email"] = self.enable_email_var.get()
        self.cfg["enable_desktop"] = self.enable_desktop_var.get()
        self.cfg["minimize_to_tray"] = self.minimize_to_tray_var.get()
        save_config(self.cfg)
        messagebox.showinfo("成功", "通知设置已保存")

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

    def _manual_export(self):
        export_dir = self.setting_vars.get("export_md_path")
        if not export_dir or not export_dir.get().strip():
            messagebox.showwarning("提示", "请先设置 MD 导出目录")
            return
        try:
            data = load_yaml(self.cfg["yaml_path"])
            export_to_md(data, export_dir.get().strip())
            messagebox.showinfo("成功", f"已导出到 {export_dir.get().strip()}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    # ==================== 通知历史 ====================

    def _build_notify_history_tab(self):
        btn_frame = ttk.Frame(self.frame_notify_history)
        btn_frame.pack(fill="x", padx=6, pady=(6, 0))
        ttk.Button(btn_frame, text="刷新", command=self._load_notify_history).pack(side="left")
        ttk.Button(btn_frame, text="清空", command=self._clear_notify_history).pack(side="left", padx=(6, 0))

        cols = ("time", "title", "message")
        self.notify_tree = ttk.Treeview(self.frame_notify_history, columns=cols, show="headings", height=20)
        self.notify_tree.heading("time", text="时间")
        self.notify_tree.heading("title", text="标题")
        self.notify_tree.heading("message", text="内容")
        self.notify_tree.column("time", width=150)
        self.notify_tree.column("title", width=200)
        self.notify_tree.column("message", width=450)

        scrollbar = ttk.Scrollbar(self.frame_notify_history, orient="vertical", command=self.notify_tree.yview)
        self.notify_tree.configure(yscrollcommand=scrollbar.set)
        self.notify_tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        scrollbar.pack(side="left", fill="y", pady=6, padx=(0, 6))

        self._load_notify_history()

    def _load_notify_history(self):
        for item in self.notify_tree.get_children():
            self.notify_tree.delete(item)
        data = load_notification_history()
        for entry in reversed(data.get("history", [])):
            self.notify_tree.insert("", "end", values=(
                entry.get("time", ""),
                entry.get("title", ""),
                entry.get("message", ""),
            ))

    def _clear_notify_history(self):
        if not messagebox.askyesno("确认", "确定要清空所有通知历史吗？"):
            return
        from storage import NOTIFICATION_HISTORY_PATH
        import json
        with open(NOTIFICATION_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump({"history": []}, f)
        self._load_notify_history()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ReminderApp()
    app.run()
