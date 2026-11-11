"""DeepSeek 调用封装（OpenAI 兼容协议，纯标准库）

Key 从 backend/.env 读取，环境变量优先。
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENV_FILE = Path(__file__).parent / ".env"


def _load_env() -> dict[str, str]:
    data: dict[str, str] = {}
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"):
        if os.environ.get(key):
            data[key] = os.environ[key]
    return data


_ENV = _load_env()
API_KEY = (_ENV.get("DEEPSEEK_API_KEY") or "").strip()
BASE_URL = (_ENV.get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com/v1").rstrip("/")
MODEL = _ENV.get("DEEPSEEK_MODEL") or "deepseek-chat"


class LLMError(RuntimeError):
    pass


def status() -> dict[str, Any]:
    hint = ""
    if API_KEY:
        hint = API_KEY[:6] + "…" + API_KEY[-4:] if len(API_KEY) > 12 else "已配置"
    return {
        "configured": bool(API_KEY),
        "model": MODEL,
        "base_url": BASE_URL,
        "key_hint": hint,
        "env_file": str(ENV_FILE),
    }


def _extract_json(text: str) -> dict | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def chat(
    messages: list[dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 900,
    timeout: int = 90,
) -> dict[str, Any]:
    """调用 DeepSeek，返回 {content, usage, elapsed_ms, model}。失败抛 LLMError。"""
    if not API_KEY:
        raise LLMError("未配置 DEEPSEEK_API_KEY（请填写 backend/.env 第 3 行）")

    url = f"{BASE_URL}/chat/completions"
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:400]
        raise LLMError(f"DeepSeek 返回 HTTP {exc.code}：{detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"无法连接 DeepSeek：{exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMError("DeepSeek 请求超时") from exc

    try:
        data = json.loads(body)
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise LLMError(f"DeepSeek 返回格式异常：{body[:300]}") from exc

    return {
        "content": content.strip(),
        "usage": data.get("usage", {}),
        "elapsed_ms": int((time.time() - started) * 1000),
        "model": data.get("model", MODEL),
    }


def parse_json_answer(text: str) -> dict | None:
    return _extract_json(text)


def mask_key(key: str) -> str:
    if not key:
        return ""
    return re.sub(r"^(.{4}).+(.{4})$", r"\1****\2", key)
