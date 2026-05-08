# 日程提醒工具

一个基于 Python 的日程提醒工具，支持桌面通知和邮件推送。

## 功能特性

- 图形化界面管理日程事件
- 支持桌面通知（使用 plyer 库）
- 支持邮件推送（SMTP）
- 灵活的提醒规则：
  - 周提醒（提前一周周一、周五）
  - 日期提醒（提前7天、3天、当天）
  - 课程提醒（前一天、当天）
  - 晚间事项提醒

## 安装依赖

```bash
pip install pyyaml plyer
```

## 配置

1. 复制配置文件示例：
   ```bash
   cp config.example.json config.json
   ```

2. 编辑 `config.json`，填入你的配置：
   ```json
   {
     "yaml_path": "你的日程.yaml文件路径",
     "smtp_server": "smtp.qq.com",
     "smtp_port": 465,
     "sender_email": "你的邮箱@qq.com",
     "sender_password": "SMTP授权码",
     "receiver_email": "接收邮箱@qq.com"
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

## 文件说明

- `reminder_gui.pyw` - 图形界面版本（无控制台窗口）
- `reminder.py` - 命令行版本
- `config.json` - 配置文件（不提交到 Git）
- `config.example.json` - 配置文件示例
- `启动提醒工具.bat` - Windows 启动脚本

## 许可证

MIT License
