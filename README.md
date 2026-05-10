# 日程提醒工具

一个基于 Python + tkinter 的日程提醒工具，支持桌面通知、邮件推送和 AI 智能添加日程。

## 功能特性

- 图形化界面管理日程事件
- 多日事件子项独立完成标记
- 支持桌面通知（使用 plyer 库）
- 支持邮件推送（SMTP）
- AI 智能解析自然语言添加日程（支持智谱 GLM、通义千问）
- 系统托盘最小化（使用 pystray）
- 可自定义字体和字号
- 可配置通知方式（邮件/桌面/托盘）
- 灵活的提醒规则：
  - 周提醒
  - 日期提醒（前一天、当天）
  - 多日事件提醒

## 安装依赖

```bash
pip install pyyaml plyer pystray Pillow requests
```

## 配置

1. 复制配置文件示例：
   ```bash
   cp config.example.json data/config.json
   ```

2. 编辑 `data/config.json`，填入你的配置：
   ```json
   {
     "yaml_path": "你的日程.yaml文件路径",
     "smtp_server": "smtp.qq.com",
     "smtp_port": 465,
     "sender_email": "你的邮箱@qq.com",
     "sender_password": "SMTP授权码",
     "receiver_email": "接收邮箱@qq.com",
     "ai_provider": "zhipu",
     "ai_model": "glm-4-flash",
     "ai_api_key": "你的API Key"
   }
   ```

3. 准备日程 YAML 文件，格式参考：

   ```yaml
   reminders:
     - name: 示例考试
       type: exam
       date: 2026-05-15
       location: 教学楼A301

     - name: 示例课程
       type: class
       start: 2026-05-10
       end: 2026-06-30
       schedule:
         - day: 周一
           period: 1-4
           location: 教室101
   ```

## 使用方法

### 图形界面

双击 `reminder_gui.pyw` 或运行：
```bash
python reminder_gui.pyw
```

### 命令行

```bash
# 检查并发送今日提醒
python reminder.py

# 查看未来7天日程
python reminder.py --list

# 发送测试通知
python reminder.py --test
```

### 定时任务

使用 Windows 任务计划程序，每天定时运行：
```bash
python reminder.py
```

## 文件结构

```
reminder-app/
├── reminder_gui.pyw    # 图形界面主程序
├── reminder.py         # 命令行版本
├── config.example.json # 配置文件示例
├── README.md
├── .gitignore
├── assets/
│   ├── 图片2.ico      # 应用图标
│   └── tray_icon.png   # 托盘图标
└── src/
    ├── config.py        # 配置管理
    ├── storage.py       # YAML/历史存储
    ├── notifications.py # 邮件和桌面通知
    ├── ai_service.py    # AI API 调用
    ├── reminder_engine.py # 提醒引擎
    └── event_dialog.py  # 事件编辑对话框
```

## 许可证

MIT License
