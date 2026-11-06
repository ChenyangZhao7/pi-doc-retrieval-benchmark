"""打分器 provider 适配层。

不同厂商的参数和用量字段不一样，集中在这里处理：
- DeepSeek：可以 thinking=disabled、temperature=0，用量有 cache_hit/cache_miss；
- Moonshot：K3.1 Pro 始终思考、temperature 固定 1.0，用量在 prompt_tokens_details。

对外只暴露 call_judge(name, system, user) 和 judge_cost(name, usage, period)。
"""

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_CONFIG = json.loads((ROOT / "config" / "judges.json").read_text(encoding="utf-8"))
CONFIG = _CONFIG["judges"]
ROUTING = _CONFIG.get("routing", {})
RUN_CONFIG = json.loads((ROOT / "config" / "run.json").read_text(encoding="utf-8"))


def get_key(env_name):
    """先读当前进程，再读 Windows 用户级环境变量（setx 写入的值）。

    env_name 可以是字符串或候选列表，例如
    ["MOONSHOT_API_KEY", "KIMI_API_KEY"]。
    """
    names = [env_name] if isinstance(env_name, str) else list(env_name)
    for name in names:
        key = os.environ.get(name)
        if key:
            return key

    # 本地密钥文件（已被 .gitignore 忽略），方便不想用 setx 的情况
    secrets_path = ROOT / ".secrets.local.json"
    if secrets_path.exists():
        try:
            secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
            for name in names:
                if secrets.get(name):
                    return secrets[name]
        except (json.JSONDecodeError, OSError):
            pass

    if os.name != "nt":
        return None
    for name in names:
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                value, _ = winreg.QueryValueEx(k, name)
                if value:
                    return value
        except OSError:
            pass

    # 兜底：某些环境用 PowerShell 才能读到
    for name in names:
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"[Environment]::GetEnvironmentVariable('{name}','User')"],
                capture_output=True, text=True, timeout=20,
            )
            key = (out.stdout or "").strip()
            if key:
                return key
        except Exception:  # noqa: BLE001
            pass
    return None


def key_source(env_name):
    """返回实际找到 key 的变量名，找不到返回 None。"""
    names = [env_name] if isinstance(env_name, str) else list(env_name)
    for name in names:
        if get_key(name):
            return name
    return None


def _extract_json(text):
    """兼容 ```json 包裹和前后废话。"""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def call_judge(name, system_prompt, user_prompt, retries=2, timeout=180):
    cfg = CONFIG[name]
    key = get_key(cfg["api_key_env"])
    if not key:
        return None, {}, f"未找到 {cfg['api_key_env']}"

    body = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 4000,
    }
    body.update(cfg.get("params", {}))
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    last_error = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            cfg["base_url"],
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"bad payload: {str(payload)[:200]}")
            choices = payload.get("choices") or []
            if not choices:
                raise ValueError(f"no choices: {str(payload)[:200]}")
            content = (choices[0]["message"].get("content") or "").strip()
            if not content:
                raise ValueError("empty content")
            return _extract_json(content), payload.get("usage", {}), None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "ignore")[:300]
            last_error = f"HTTP {exc.code}: {detail}"
            # 4xx 里只有 429 值得重试
            if exc.code != 429:
                break
        except (urllib.error.URLError, OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
        time.sleep(1 + attempt)
    return None, {}, str(last_error)


def billing_mode(name):
    cfg = CONFIG[name]
    price = cfg.get("pricing") or {}
    return price.get("billing", "per_token")


def judge_cost(name, usage, period):
    """按各厂商官方价重算费用；返回 (金额, 币种)。订阅制返回 0。"""
    cfg = CONFIG[name]
    price = cfg.get("pricing")
    if not price or not usage:
        return None, None
    if price.get("billing") == "subscription":
        return 0.0, price["currency"]

    if cfg["provider"] == "deepseek":
        p = price["peak"] if period == "peak" else price["off_peak"]
        hit = usage.get("prompt_cache_hit_tokens", 0)
        miss = usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0))
        out = usage.get("completion_tokens", 0)
        cost = (
            hit / 1e6 * p["cache_read"]
            + miss / 1e6 * p["input"]
            + out / 1e6 * p["output"]
        )
        return round(cost, 6), price["currency"]

    # moonshot：prompt_tokens 是总数，明细在 prompt_tokens_details
    details = usage.get("prompt_tokens_details") or {}
    total_in = usage.get("prompt_tokens", 0)
    cached = details.get("cached_tokens", 0)
    written = details.get("cache_write_tokens", 0)
    miss = max(total_in - cached - written, 0)
    out = usage.get("completion_tokens", 0)
    cost = (
        miss / 1e6 * price["input"]
        + cached / 1e6 * price["cache_read"]
        + written / 1e6 * price.get("cache_write", price["input"])
        + out / 1e6 * price["output"]
    )
    return round(cost, 6), price["currency"]


def to_usd(amount, currency):
    """统一折算成美元，便于跨厂商比较。汇率是可配置的假设值。"""
    if amount is None:
        return None
    if currency == "USD":
        return amount
    rate = RUN_CONFIG.get("fx_cny_per_usd", 7.1)
    return round(amount / rate, 6)
