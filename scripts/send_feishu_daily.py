#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_json(path):
    if not path.exists():
        return {}
    return json.load(open(path, encoding="utf-8"))

def site_url():
    return os.environ.get("PUBLIC_SITE_URL", "https://xiaozhiyun.github.io/ai-news-radar/")

def sign(secret, timestamp):
    msg = f"{timestamp}\n{secret}".encode("utf-8")
    return base64.b64encode(hmac.new(msg, b"", hashlib.sha256).digest()).decode("utf-8")

def build_text():
    brief = load_json(ROOT / "data" / "daily-brief.json")
    latest = load_json(ROOT / "data" / "latest-24h.json")
    status = load_json(ROOT / "data" / "source-status.json")

    items = brief.get("items") or latest.get("items") or []
    lines = [
        "AI News Radar 日报",
        "",
        f"更新时间：{latest.get('generated_at') or brief.get('generated_at') or 'unknown'}",
        f"过去 24 小时：AI 信号 {latest.get('total_items', brief.get('total_items', 0))} 条",
        f"来源状态：{status.get('successful_sites', 0)} 个正常 / {status.get('failed_sites', 0)} 个失败",
        "",
        "今日重点：",
    ]

    for i, item in enumerate(items[:8], 1):
        title = item.get("title") or "未命名更新"
        source = item.get("source_name") or item.get("source") or "未知来源"
        url = item.get("primary_url") or item.get("url") or ""
        lines.append(f"{i}. {title}（{source}）")
        if url:
            lines.append(f"   {url}")

    if not items:
        lines.append("暂无精选条目，请打开网页查看完整列表。")

    lines.append("")
    lines.append(f"打开完整雷达：{site_url()}")
    return "\n".join(lines)

def main():
    webhook = os.environ["FEISHU_BOT_WEBHOOK"]
    payload = {
        "msg_type": "text",
        "content": {"text": build_text()},
    }

    secret = os.environ.get("FEISHU_BOT_SECRET")
    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = sign(secret, timestamp)

    req = urllib.request.Request(
        webhook,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        print(resp.read().decode("utf-8", errors="replace"))

if __name__ == "__main__":
    main()
