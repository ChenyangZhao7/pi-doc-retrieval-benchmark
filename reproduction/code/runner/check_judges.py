"""检查每个打分器的 key、连通性、JSON 模式和费用。

用法：
    python runner/check_judges.py
    python runner/check_judges.py --judge kimi-k3.1-pro

输出每个打分器：key 来源、HTTP 是否成功、耗时、返回的 JSON、单次调用费用。
这是发正式实验前的第一道自检，避免跑到一半才发现 401。
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import judges  # noqa: E402

SYSTEM = "你是接口自检助手。只输出 json，不要输出其他内容。"
USER = '请原样输出：{"ok": true}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default=None, choices=sorted(judges.CONFIG))
    args = ap.parse_args()

    names = [args.judge] if args.judge else list(judges.CONFIG)
    period = "peak" if datetime.now(timezone.utc).weekday() < 5 and (
        1 <= datetime.now(timezone.utc).hour < 4
        or 6 <= datetime.now(timezone.utc).hour < 10
    ) else "off-peak"

    print(f"{'打分器':16} {'key':10} {'状态':8} {'耗时':>8}  {'费用':>18}  JSON")
    print("-" * 90)
    ok_all = True

    for name in names:
        cfg = judges.CONFIG[name]
        source = judges.key_source(cfg["api_key_env"])
        if not source:
            names_str = cfg["api_key_env"]
            names_str = [names_str] if isinstance(names_str, str) else names_str
            print(f"{name:16} {'缺失':10} {'跳过':8} {'-':>8}  {'-':>18}  未设置 {' / '.join(names_str)}")
            ok_all = False
            continue

        start = time.time()
        result, usage, error = judges.call_judge(name, SYSTEM, USER, retries=0)
        elapsed = (time.time() - start) * 1000

        native, currency = judges.judge_cost(name, usage, period)
        usd = judges.to_usd(native, currency)
        if judges.billing_mode(name) == "subscription":
            cost = "订阅（0 边际成本）"
        else:
            cost = f"{native} {currency} (${usd})" if native is not None else "-"

        if result is None:
            print(f"{name:16} {source:10} {'失败':8} {elapsed:7.0f}ms  {cost:>18}  {error}")
            ok_all = False
        else:
            print(f"{name:16} {source:10} {'OK':8} {elapsed:7.0f}ms  {cost:>18}  {json.dumps(result, ensure_ascii=False)}")

    print()
    if ok_all:
        print("全部打分器可用。")
    else:
        print("有打分器不可用，先修 key 或网络，不要开始批量打分。")


if __name__ == "__main__":
    main()
