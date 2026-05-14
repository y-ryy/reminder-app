# 日程提醒工具

一个基于 Python + tkinter 的桌面日程提醒工具，支持邮件推送、桌面通知、AI 智能添加日程和系统托盘最小化。

## 功能特性

- **事件管理**：添加/编辑/删除日程事件，支持单日事件和多日周期事件
- **多日事件子项**：实训、课程等多日事件可按天独立标记完成，显示 `[已完成/总数]` 进度
- **智能排序**：部分完成的多日事件按下一个待办日期排序
- **搜索筛选**：按名称搜索、按类型（考试/上课/实训/其他）筛选
- **邮件通知**：SMTP_SSL 邮件推送，支持 QQ 邮箱等
- **桌面通知**：基于 plyer 的系统桌面通知
- **AI 助手**：自然语言输入自动解析为日程事件（支持智谱 GLM、通义千问）
- **通知历史**：所有发送的通知自动记录，可查看和清空
- **系统托盘**：启动即显示托盘图标，支持重启/退出
- **MD 导出**：日程变更自动导出为 Markdown 文件，支持手动导出，可配合 Obsidian 使用
- **自动提醒**：程序启动时发送今日/明日汇总，后台每 60 秒检查到期提醒
- **自动完成**：过期事件自动标记完成（多日事件以结束日期为准）
- **补发机制**：程序重启后自动补发错过的提醒
- **线程安全**：YAML 读写使用锁保护，避免并发损坏

## 安装依赖

```bash
pip install pyyaml plyer pystray Pillow requests
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/y-ryy/reminder-app.git
cd reminder-app
```

### 2. 创建配置文件

```bash
# 复制示例配置
copy config.example.json data\config.json
```

### 3. 编辑配置

打开 `data/config.json`，按需修改以下内容：

```json
{
  "yaml_path": "D:\\你的路径\\日程.yaml",
  "smtp_server": "smtp.qq.com",
  "smtp_port": 465,
  "sender_email": "你的邮箱@qq.com",
  "sender_password": "你的SMTP授权码",
  "receiver_email": "接收邮箱@qq.com",
  "ai_provider": "zhipu",
  "ai_model": "glm-4-flash",
  "ai_api_key": "你的API Key",
  "enable_email": true,
  "enable_desktop": true,
  "minimize_to_tray": false,
  "semester_start": "2026-03-02",
  "export_md_path": "",
  "font_family": "微软雅黑",
  "font_size": 14
}
```

### 4. 启动程序

```bash
python reminder_gui.pyw
```

## 配置详解

### 基础配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `yaml_path` | string | `""` | 日程数据文件路径（.yaml），首次使用需手动创建或由程序自动创建 |
| `semester_start` | string | `"2026-03-02"` | 学期起始日期（YYYY-MM-DD），用于计算周次 |
| `export_md_path` | string | `""` | 日程导出目录，每次变更自动生成 `日程MMDD.md`，同日多次追加 `_01` `_02`，为空不导出 |
| `font_family` | string | `"微软雅黑"` | 界面字体，可选：微软雅黑、宋体、黑体、Arial、Consolas |
| `font_size` | number | `14` | 界面字号，范围 8~36 |

### 邮件配置

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `smtp_server` | string | SMTP 服务器地址，如 `smtp.qq.com`、`smtp.163.com` |
| `smtp_port` | number | SMTP 端口，QQ 邮箱为 `465`，163 邮箱为 `465` |
| `sender_email` | string | 发件人邮箱地址 |
| `sender_password` | string | SMTP 授权码（非邮箱密码） |
| `receiver_email` | string | 收件人邮箱地址 |

**QQ 邮箱获取授权码：** 登录 QQ 邮箱 → 设置 → 账户 → POP3/IMAP/SMTP 服务 → 开启 SMTP → 生成授权码

### 通知配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_email` | bool | `true` | 启用邮件通知 |
| `enable_desktop` | bool | `true` | 启用桌面通知 |
| `minimize_to_tray` | bool | `false` | 关闭窗口时最小化到系统托盘而非退出 |

### AI 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `ai_provider` | string | `"zhipu"` | AI 服务商，可选 `zhipu`（智谱）、`qwen`（通义千问） |
| `ai_model` | string | `"glm-4-flash"` | AI 模型 ID |
| `ai_api_key` | string | `""` | AI API Key |

**免费模型推荐：**
- 智谱 GLM：`glm-4-flash`（免费）— 在 [智谱开放平台](https://open.bigmodel.cn/) 注册获取 API Key
- 通义千问：`qwen-turbo`（免费）— 在 [阿里云百炼](https://bailian.console.aliyun.com/) 注册获取 API Key

## 使用说明

### 事件类型

| 类型代码 | 含义 | 示例 |
|----------|------|------|
| `exam` | 考试 | 期末考试、单元测试 |
| `class` | 上课 | 每周一的数据库课 |
| `training` | 实训 | 为期两周的 EDA 实训 |
| `other` | 其他 | 提交作业、答辩 |

### 事件精度

| 精度 | 填写字段 | 适用场景 |
|------|----------|----------|
| 只有周次 | `week` | 如"第8周"，不指定具体日期 |
| 具体日期 | `date` | 如"2026-05-15"，单日事件 |
| 多日周期 | `start` + `end` + `schedule` | 如实训周，跨多天且每周几有固定安排 |

### 提醒规则

| 事件类型 | 提醒时间点 |
|----------|-----------|
| 只有周次 | 前一周周一 20:00、前一周周日 20:00 |
| 具体日期 | 前一天 20:00、当天（按时间段） |
| 多日周期 | 开始前一天 20:00、每个周一 07:30 |

当天时间段对应提醒时间：

| 时段 | 含义 | 提醒时间 |
|------|------|----------|
| `1-4` | 上午 1~4 节 | 06:00 |
| `5-8` | 下午 5~8 节 | 10:00 |
| `evening` | 晚课 | 14:00 |
| `全天` | 全天 | 07:00 |

### YAML 数据格式

```yaml
reminders:
  # 单日事件
  - name: 数据库期末考试
    type: exam
    date: 2026-06-20
    time: evening
    location: 教学楼A301

  # 只有周次的事件
  - name: 选修课论文
    type: other
    week: 第12周

  # 多日周期事件（实训）
  - name: EDA实训
    type: training
    start: 2026-05-18
    end: 2026-05-23
    schedule:
      - day: 周二
        period: 3-4
        location: 新安215
      - day: 周四
        period: evening
        location: 电气楼507
      - day: 周五
        period: 全天
        location: 电气楼507
```

### AI 助手使用

在"AI 助手"页签中输入自然语言，AI 会自动解析为事件：

```
下周三下午数据库考试，地点主楼301
```

```
5月18日到5月23日EDA实训，周二3-4节在新安215，周四晚课在电气楼507，周五全天在电气楼507
```

解析结果会弹出编辑对话框，确认后自动保存。

### 右键菜单

在事件列表中右键点击可使用：
- **添加**：手动添加新事件
- **编辑**：修改选中事件
- **删除**：删除选中事件（需确认）
- **刷新**：重新加载事件列表
- **测试推送**：手动触发选中事件的桌面通知和邮件

### MD 导出

在设置页填写"MD 导出目录"（如 `D:\ObsidianVault\日程`），每次日程变更会自动导出为独立文件：

- 文件命名：`日程0514.md`（5月14日导出）
- 同日多次导出：`日程0514_01.md`、`日程0514_02.md`...
- 也可点击"手动导出"按钮立即生成

导出目录设为 Obsidian vault 路径，配合 Remotely Save 插件可自动同步到云端。

## 文件结构

```
reminder-app/
├── reminder_gui.pyw          # 图形界面主程序
├── config.example.json       # 配置文件示例
├── README.md
├── .gitignore
├── assets/
│   ├── 图片2.ico             # 窗口和托盘图标
│   └── tray_icon.png         # 托盘图标（PNG）
└── src/
    ├── config.py             # 配置管理、AI 服务商定义
    ├── storage.py            # YAML 读写、对话历史、通知历史
    ├── notifications.py      # 邮件和桌面通知发送
    ├── ai_service.py         # AI API 调用与响应解析
    ├── reminder_engine.py    # 提醒生成、自动完成、定时检查
    └── event_dialog.py       # 事件编辑对话框
```

## 许可证

MIT License
