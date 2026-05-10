"""事件编辑对话框"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date


class EventDialog:
    def __init__(self, parent, title, reminder=None, callback=None):
        self.callback = callback
        self.reminder = reminder or {}
        self.result = None
        self.schedule_list = []

        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.geometry("520x580")
        self.win.resizable(False, False)
        self.win.grab_set()

        self._build()
        if reminder:
            self._fill(reminder)

    def _build(self):
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

        ttk.Label(info_frame, text="类型: exam/class/training/other", font=("", 12),
                  foreground="gray").grid(row=4, column=0, columnspan=4, sticky="w")

        sched_frame = ttk.LabelFrame(self.win, text="每日安排（用于多日事件，如实训、课程）", padding=10)
        sched_frame.pack(fill="both", expand=True, padx=10, pady=5)

        cols = ("day", "period", "location")
        self.sched_tree = ttk.Treeview(sched_frame, columns=cols, show="headings", height=5)
        self.sched_tree.heading("day", text="星期")
        self.sched_tree.heading("period", text="时段")
        self.sched_tree.heading("location", text="地点")
        self.sched_tree.column("day", width=80)
        self.sched_tree.column("period", width=100)
        self.sched_tree.column("location", width=200)
        self.sched_tree.pack(fill="both", expand=True, pady=(0, 8))

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
        valid_types = ("exam", "class", "training", "other")
        if rem.get("type") and rem["type"] not in valid_types:
            messagebox.showwarning("提示", f"类型只能是：{', '.join(valid_types)}")
            return
        if self.schedule_list:
            rem["schedule"] = self.schedule_list
        if self.callback:
            self.callback(rem)
        self.win.destroy()
