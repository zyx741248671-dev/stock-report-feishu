import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "stock_report" / "config.json"


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def build_prompt(report_type: str, config: dict) -> str:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    date_text = now.strftime("%Y年%m月%d日")
    weekday = "一二三四五六日"[now.weekday()]
    holdings_text = "\n".join(
        f"- {item['name']}（{item['code']}）：{item['theme']}"
        for item in config["holdings"]
    )

    if report_type == "morning":
        title = "早盘前简报"
        timing = (
            "请结合隔夜美股与科技股表现、美元/人民币汇率、美国利率、原油、黄金、"
            "国内盘前政策与新闻、行业消息、上市公司公告、A股前一交易日结构，"
            "分析今天开盘前应该怎么观察。"
        )
        action_focus = "今天开盘前我该怎么做"
    else:
        title = "收盘复盘"
        timing = (
            "请结合今天A股走势、成交与板块轮动、个股公告与财报/业绩预告、资金面、"
            "国内宏观经济与政策、海外市场、汇率、大宗商品和利率环境，"
            "分析今天收盘后应该怎么调整观察。"
        )
        action_focus = "今天收盘后我该怎么做"

    return f"""
你是一位耐心、谨慎、善于给小白解释投资逻辑的A股研究助手。

今天是北京时间 {date_text}，星期{weekday}。请生成一份《{date_text} A股持仓{title}》。

用户是投资小白，请务必做到：
- 用非常通俗、直接、容易理解的中文。
- 少用专业术语；如果必须用，请立刻用生活化语言解释。
- 先给结论，再解释原因。
- 不要只说“关注”“留意”，要给更明确的研究型动作建议，例如：持有、观察、不加仓、逢高减一点、等信号再买。
- 不要承诺收益，不要说“必涨”“稳赚”。
- 明确写一句：这不是持牌投顾建议，最终由用户自己决定。

用户当前持仓：
{holdings_text}

请重点覆盖：
{timing}

报告结构必须如下：

1. 今天一句话结论
用一句非常直白的话说明今天整体该谨慎、持有观察、还是可以小幅进攻。

2. {action_focus}
用 3-5 条直接建议告诉用户今天怎么做。请尽量具体。

3. 为什么今天市场会这样
用小白能听懂的话解释国内、海外、政策、汇率、利率、大宗商品等因素。每个因素都说明“为什么会影响我的股票”。

4. 五只持仓逐只分析
每只股票都按这个结构写：
- 小白版解释：这家公司主要靠什么赚钱。
- 今天影响它的关键因素。
- 直接建议：持有/观察/不加仓/逢高减一点/等信号再买。
- 仓位建议：给百分比区间，并用“如果总资金是10万元，大约是多少钱”解释。
- 需要盯的信号：最多3条。
- 最大风险：一句话。

5. 红黄绿灯总结
- 绿色：可以继续持有或重点关注。
- 黄色：先观察等待。
- 红色：不建议加仓或需要控制风险。

6. 可以额外关注的板块或股票
最多推荐 2 个方向，每个方向最多 2 只A股。必须说明：
- 为什么现在看它。
- 什么情况更适合买。
- 什么情况说明看错了。

请联网核对最新公开信息。若某些实时行情或公告无法稳定获取，请在报告里标明“数据口径限制”，不要编造具体涨跌幅或成交额。
""".strip()


def generate_report(report_type: str) -> str:
    config = load_config()
    client = OpenAI(api_key=require_env("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL") or "gpt-4.1"
    prompt = build_prompt(report_type, config)

    response = client.responses.create(
        model=model,
        input=prompt,
        tools=[{"type": "web_search_preview"}],
    )

    text = getattr(response, "output_text", None)
    if text:
        return text.strip()

    parts = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            value = getattr(content, "text", None)
            if value:
                parts.append(value)
    if not parts:
        raise RuntimeError("OpenAI response did not contain report text.")
    return "\n".join(parts).strip()


def feishu_sign(timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def send_feishu_text(text: str) -> None:
    webhook = require_env("FEISHU_WEBHOOK")
    secret = require_env("FEISHU_SECRET")

    max_chars = 3200
    chunks = [text[i : i + max_chars] for i in range(0, len(text), max_chars)]
    total = len(chunks)

    for index, chunk in enumerate(chunks, start=1):
        timestamp = str(int(time.time()))
        payload = {
            "timestamp": timestamp,
            "sign": feishu_sign(timestamp, secret),
            "msg_type": "text",
            "content": {
                "text": f"【A股自动简报 {index}/{total}】\n{chunk}"
                if total > 1
                else f"【A股自动简报】\n{chunk}"
            },
        }
        request = urllib.request.Request(
            webhook,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
        result = json.loads(body)
        if result.get("code") not in (0, None) or result.get("StatusCode") not in (0, None):
            raise RuntimeError(f"Feishu send failed: {body}")
        time.sleep(0.5)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--type",
        choices=["morning", "evening"],
        default=os.getenv("REPORT_TYPE", "morning"),
        help="morning for 08:30 brief, evening for 17:30 review",
    )
    args = parser.parse_args()

    report = generate_report(args.type)
    send_feishu_text(report)
    print("Report generated and sent to Feishu successfully.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
