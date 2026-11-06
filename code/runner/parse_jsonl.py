"""把 pi 的 JSONL 事件流解析成一行指标。

只依赖标准库。既可以被 run_one.py 导入，也可以单独运行：
    python runner/parse_jsonl.py runs/G1/S/q001_r1.jsonl
"""

import json
import sys


def read_events(path):
    """读取 JSONL，自动处理 UTF-8 / UTF-16 BOM。

    PowerShell 的 `>` 会写成 UTF-16，所以这里必须兼容。
    """
    raw = open(path, "rb").read()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig")
    else:
        text = raw.decode("utf-8", errors="replace")

    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # 不静默丢弃：坏行会在 parse_events 里计入 bad_lines
            events.append({"type": "__bad_line__", "raw": line[:200]})
    return events


def _text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for part in content or []:
        if isinstance(part, dict) and part.get("type") == "text":
            parts.append(part.get("text") or "")
    return "".join(parts)


def parse_events(events):
    tools_by_name = {}
    tool_ms = 0
    tool_errors = 0
    tool_calls = []

    turns = 0
    assistant_messages = 0
    tokens = {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_write": 0,
        "reasoning": 0,
        "total": 0,
    }
    cost = 0.0

    compactions = 0
    compact_before = 0
    compact_after = 0

    bad_lines = 0
    final_answer = ""
    pseudo_tool_call = False

    for e in events:
        t = e.get("type")
        if t == "__bad_line__":
            bad_lines += 1
            continue

        if t == "turn_start":
            turns += 1

        elif t == "tool_execution_start":
            name = e.get("toolName") or "?"
            tools_by_name[name] = tools_by_name.get(name, 0) + 1
            tool_calls.append({"name": name, "args": e.get("args")})

        elif t == "tool_execution_end":
            tool_ms += e.get("durationMs") or 0
            if e.get("isError"):
                tool_errors += 1

        elif t == "message_end":
            msg = e.get("message") or {}
            if msg.get("role") == "assistant":
                assistant_messages += 1
                u = msg.get("usage") or {}
                tokens["input"] += u.get("input") or 0
                tokens["output"] += u.get("output") or 0
                tokens["cache_read"] += u.get("cacheRead") or 0
                tokens["cache_write"] += u.get("cacheWrite") or 0
                tokens["reasoning"] += u.get("reasoning") or 0
                tokens["total"] += u.get("totalTokens") or 0
                cost += (u.get("cost") or {}).get("total") or 0

                text = _text_of(msg.get("content"))
                if text:
                    final_answer = text
                if "<||DSML||" in text or "invoke name=" in text:
                    pseudo_tool_call = True

        elif t == "compaction_end":
            compactions += 1
            compact_before += e.get("tokensBefore") or (e.get("result") or {}).get("tokensBefore") or 0
            compact_after += e.get("estimatedTokensAfter") or (e.get("result") or {}).get("estimatedTokensAfter") or 0

    total_tools = sum(tools_by_name.values())
    return {
        "turns": turns,
        "assistant_messages": assistant_messages,
        "tool_calls_total": total_tools,
        "tool_calls_by_name": tools_by_name,
        "tool_ms": round(tool_ms),
        "tool_errors": tool_errors,
        "tool_calls": tool_calls,
        "tokens": tokens,
        "cost_usd": round(cost, 6),
        "compactions": compactions,
        "compaction_tokens_before": compact_before,
        "compaction_tokens_after": compact_after,
        "pseudo_tool_call": pseudo_tool_call,
        "answer_chars": len(final_answer),
        "answer": final_answer,
        "bad_lines": bad_lines,
    }


def parse_file(path):
    return parse_events(read_events(path))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python runner/parse_jsonl.py <run.jsonl>")
        raise SystemExit(2)
    print(json.dumps(parse_file(sys.argv[1]), ensure_ascii=False, indent=2))
