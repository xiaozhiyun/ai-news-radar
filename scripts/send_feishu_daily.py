#!/usr/bin/env python3
"""Send the AI News Radar daily brief to a Feishu custom bot webhook."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def infer_site_url() -> str:
    explicit = os.environ.get("PUBLIC_SITE_URL", "").strip()
    if explicit:
        return explicit

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}/"

    return "http://localhost:8080/"


def feishu_signature(secret: str, timestamp: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def pick_top_items(brief: dict, latest: dict, limit: int = 8) -> list[dict]:
    items = brief.get("items") or []
    if not items:
        items = latest.get("items") or latest.get("items_ai") or []
    return items[:limit]


def format_message() -> str:
    brief = load_json(ROOT / "data" / "daily-brief.json")
    latest = load_json(ROOT / "data" / "latest-24h.json")
    status = load_json(ROOT / "data" / "source-status.json")

    generated_at = latest.get("generated_at") or brief.get("generated_at") or "unknown"
    total_ai = latest.get("total_items") or brief.get("total_items") or 0
    total_raw = latest.get("total_items_raw") or latest.get("total_items_all_mode") or 0
    successful_sites = status.get("successful_sites", 0)
    failed_sites = status.get("failed_sites", 0)
    site_url = infer_site_url()

    lines = [
        "AI News Radar 日报",
        "",
        f"更新时间：{generated_at}",
        f"过去 24 小时：AI 信号 {total_ai} 条 / 原始覆盖 {total_raw} 条",
        f"来源状态：{successful_sites} 个正常 / {failed_sites} 个失败",
        "",
        "今日重点：",
    ]

    top_items = pick_top_items(brief, latest)
    if not top_items:
        lines.append("暂无精选条目，请查看网页完整列表。")
    else:
        for index, item in enumerate(top_items, 1):
            title = str(item.get("title") or "未命名更新").strip()
            source = item.get("source_name") or item.get("source") or "未知来源"
            url = item.get("primary_url") or item.get("url") or ""
            line = f"{index}. {title}（{source}）"
            if url:
                line += f"\n   {url}"
            lines.append(line)

    lines.extend(["", f"打开完整雷达：{site_url}"])
    return "\n".join(lines)


def send_to_feishu(text: str) -> None:
    webhook = os.environ.get("FEISHU_BOT_WEBHOOK", "").strip()
    if not webhook:
        raise RuntimeError("FEISHU_BOT_WEBHOOK is not set")

    payload: dict[str, object] = {
        "msg_type": "text",
        "content": {"text": text},
    }

    secret = os.environ.get("FEISHU_BOT_SECRET", "").strip()
    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = feishu_signature(secret, timestamp)

    request = urllib.request.Request(
        webhook,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise RuntimeError(f"Feishu webhook failed: HTTP {response.status} {body}")
        try:
            result = json.loads(body)
        except json.JSONDecodeError:
            result = {}
        if result.get("StatusCode") not in (None, 0) or result.get("code") not in (None, 0):
            raise RuntimeError(f"Feishu webhook returned error: {body}")


def main() -> int:
    try:
        send_to_feishu(format_message())
    except (OSError, RuntimeError, urllib.error.URLError) as exc:
        print(f"Failed to send Feishu daily brief: {exc}", file=sys.stderr)
        return 1
    print("Feishu daily brief sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
