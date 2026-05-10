"""AI API 调用"""

import json
from datetime import datetime, date

from config import AI_PROVIDERS


def call_ai_api(cfg, user_input):
    """调用 AI API 解析日程，返回 (event_data, error_msg)"""
    import requests

    provider_id = cfg.get("ai_provider", "zhipu")
    provider = AI_PROVIDERS.get(provider_id)
    if not provider:
        return None, "未知的 AI 服务商"

    api_key = cfg["ai_api_key"]
    model = cfg.get("ai_model", provider["default_model"])
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

        ai_content = result["choices"][0]["message"]["content"].strip()

        if "```" in ai_content:
            json_str = ai_content.split("```")[1]
            if json_str.startswith("json"):
                json_str = json_str[4:]
        else:
            json_str = ai_content

        event_data = json.loads(json_str.strip())

        if "name" not in event_data:
            return None, "AI 返回的数据缺少事项名称"

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
                    entry["day"] = weekday_names[start_date.weekday()]
                    key = (entry.get("day"), entry.get("period"))
                    if key not in seen:
                        seen.add(key)
                        unique_schedule.append(entry)
                event_data["schedule"] = unique_schedule
            except ValueError:
                pass

        # 过滤空字段
        cleaned_data = {}
        for key, val in event_data.items():
            if val is None or val == "":
                continue
            if key in ["date", "start", "end"]:
                cleaned_data[key] = str(val)
            else:
                cleaned_data[key] = val

        return cleaned_data, None

    except requests.exceptions.Timeout:
        return None, "请求超时，请检查网络后重试"
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            return None, "API Key 无效，请检查设置"
        elif e.response.status_code == 429:
            return None, "API 余额不足或请求过于频繁"
        else:
            return None, f"请求失败：{e}"
    except json.JSONDecodeError:
        return None, f"AI 返回格式错误：\n{ai_content}"
    except Exception as e:
        return None, f"发生错误：{e}"
