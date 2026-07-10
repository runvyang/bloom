"""
Daily offline task: compress old session rounds into memory log.

Run once per day (e.g., via cron) to:
1. Scan all users' session logs
2. For logs with >20 rounds, compress the oldest rounds into {course}_mem.log
3. Keep only the most recent 20 rounds in the session log
4. Use LLM to create meaningful summaries when available
"""
import os
from session_store import (get_all_messages, get_compressed_mem, append_compressed_mem,
                           count_rounds, needs_compression, _log_path)
from llm import OpenRouterClient


def compress_with_llm(messages: list, course: str, existing_mem: str) -> str:
    """Use LLM to compress old messages into a concise summary."""
    if not messages:
        return ""

    # Build conversation transcript from messages
    transcript = ""
    for m in messages:
        role = "学生" if m.get("role") == "user" else "老师"
        content = m.get("content", "")[:500]  # Truncate long messages
        transcript += f"[{role}]: {content}\n"

    llm = OpenRouterClient()
    prompt = f"""请将以下课堂对话压缩为一段简洁的学习摘要（200字以内），重点记录：
1. 学生学习了哪些知识点
2. 掌握程度有什么变化
3. 发现了什么误解或薄弱点
4. 当前的教学计划是什么

{('已有的学习记忆：' + existing_mem[:500]) if existing_mem else ''}

课堂对话：
{transcript}

请输出压缩摘要："""

    try:
        response = llm.chat([
            {"role": "user", "content": prompt}
        ], stream=False)
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM compression failed: {e}")
        # Fallback: simple truncation summary
        return _simple_compress(messages)


def _simple_compress(messages: list) -> str:
    """Simple compression without LLM — keep first 100 chars of each message."""
    lines = []
    for m in messages:
        role = "学生" if m.get("role") == "user" else "老师"
        content = m.get("content", "")[:150]
        lines.append(f"{role}: {content}")
    return "历史对话摘要：\n" + "\n".join(lines)


def compress_all_users(use_llm: bool = True):
    """Scan all users and compress session logs that need it."""
    student_dir = "data/student"
    if not os.path.exists(student_dir):
        return {"compressed": 0, "users": 0}

    total = 0
    users_done = 0

    for username in os.listdir(student_dir):
        user_path = os.path.join(student_dir, username)
        if not os.path.isdir(user_path):
            continue

        user_compressed = False
        for fname in os.listdir(user_path):
            if not fname.endswith("_session.log"):
                continue
            course = fname.replace("_session.log", "")

            if not needs_compression(username, course):
                continue

            # Get all messages
            all_msgs = get_all_messages(username, course)
            user_count = len([m for m in all_msgs if m.get("role") == "user"])
            if user_count <= 20:
                continue

            # Separate old (to compress) from recent (to keep)
            kept = []
            user_seen = 0
            for m in reversed(all_msgs):
                kept.insert(0, m)
                if m.get("role") == "user":
                    user_seen += 1
                    if user_seen >= 20:
                        break

            old_msgs = all_msgs[:-len(kept)] if len(kept) < len(all_msgs) else []
            if not old_msgs:
                continue

            existing_mem = get_compressed_mem(username, course)
            if use_llm:
                summary = compress_with_llm(old_msgs, course, existing_mem)
            else:
                summary = _simple_compress(old_msgs)

            if summary:
                append_compressed_mem(username, course, summary)

            # Rewrite session log with only kept messages
            path = _log_path(username, course)
            with open(path, "w", encoding="utf-8") as f:
                import json
                for m in kept:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")

            user_compressed = True
            total += 1

        if user_compressed:
            users_done += 1

    return {"compressed": total, "users": users_done}


if __name__ == "__main__":
    result = compress_all_users(use_llm=True)
    print(f"Compression done: {result['compressed']} sessions across {result['users']} users")
