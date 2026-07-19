from llm import OpenRouterClient
from memory import MemoryManager
from utils import read_file, append_file, copy_file, write_file
from storage import save_learning_record, extract_knowledge_points, init_storage
from session_store import (append_to_session, get_recent_rounds, get_compressed_mem,
                           mark_session_active, is_new_session, mark_checkin_sent,
                           needs_compression, truncate_and_compress, migrate_old_sessions,
                           dedup_session_log)
from datetime import datetime
import json
import os
from typing import List, Dict

llm = OpenRouterClient()
memory = MemoryManager()
init_storage()

# Simple file cache: path -> (mtime, content)
_file_cache = {}

# Pending checkin greetings — flushed to session log only if student responds
_pending_checkins = {}  # key: (user_id, course) -> greeting_text

def _read_cached(path: str) -> str:
    mtime = os.path.getmtime(path)
    if path in _file_cache and _file_cache[path][0] == mtime:
        return _file_cache[path][1]
    content = read_file(path)
    _file_cache[path] = (mtime, content)
    return content


def format_delta(delta: Dict) -> str:
    parts = [
        f"知识点：{delta['grade']}·{delta.get('module', '')}·{delta['knowledge_point']}（{delta['difficulty']}）",
        f"掌握度从'{delta['previous_mastery']}'变为'{delta['new_mastery']}'",
        f"原因：{delta['delta_reason']}",
        f"新增误解：{delta['misconception_added']}"
    ]
    return "\n  ".join(parts)


def format_teaching_plan(plan: Dict) -> str:
    parts = [
        f"下一步动作：{plan['next_action']}",
        f"目标：{plan['target']['grade']}·{plan['target']['knowledge_point']}（{plan['target']['difficulty']}）",
        f"理由：{plan['reason']}",
        f"建议活动：{plan['proposed_activity']}",
        f"优先级：{plan['priority']}（{'最高' if plan['priority']==1 else '正常' if plan['priority']==2 else '可推迟'}）",
    ]
    return "\n".join(parts)


def merge_to_text(json_data: Dict) -> str:
    text_parts = []
    deltas = json_data.get('model_update_delta', [])
    if deltas:
        text_parts.append("【学生模型更新】")
        for i, d in enumerate(deltas, 1):
            text_parts.append(f"{i}. {format_delta(d)}")
    else:
        text_parts.append("【学生模型更新】本次无变化。")

    plan = json_data.get('teaching_plan', {})
    if plan:
        text_parts.append("\n【教学计划】")
        text_parts.append(format_teaching_plan(plan))
    else:
        text_parts.append("\n【教学计划】无特别计划。")

    return "\n\n".join(text_parts)


def _build_context(user_id: str, course: str, user_input: str = "") -> dict:
    """Build the full context for the LLM prompt."""

    # Migrate old sessions on first access
    migrate_old_sessions(user_id)

    # One-time dedup of any duplicates from buggy migration
    dedup_session_log(user_id, course)

    # Auto-compress if needed
    if needs_compression(user_id, course):
        truncate_and_compress(user_id, course)

    # Load recent rounds (max 20)
    recent_msgs = get_recent_rounds(user_id, course, max_rounds=20)
    session_text = ""
    for m in recent_msgs:
        role_label = "学生" if m.get("role") == "user" else "老师"
        session_text += f"[{role_label}]: {m.get('content', '')}\n"

    # Load compressed memory
    compressed_mem = get_compressed_mem(user_id, course)

    # Load mem0 context
    if user_input:
        mem_context = memory.search(user_id, user_input)
        related_sessions = "\n".join([m['memory'] for m in mem_context["results"]])
    else:
        related_sessions = ""

    # Load course materials: course_map (readonly) + student_progress (deltas) + background (profile)
    course_map_path = f"data/student/{user_id}/{course}_map.md"
    template_path = f"courses/{course}/course_map.md"
    if not os.path.exists(course_map_path):
        copy_file(template_path, course_map_path)
    course_map = _read_cached(course_map_path)

    progress_path = f"data/student/{user_id}/{course}_progress.md"
    if not os.path.exists(progress_path):
        write_file(progress_path, "")
    student_progress = read_file(progress_path)

    student_state = course_map + "\n" + student_progress
    # Inject user profile if available; auto-migrate from state header on first access
    profile_path = f"data/student/{user_id}/profile.json"
    profile = {}
    if os.path.exists(profile_path):
        profile = json.loads(read_file(profile_path))

    # Auto-migrate: extract initial background from state header if not yet in profile
    if not profile.get(course) and student_state:
        import re
        m = re.search(r'\*\*初始状态说明\*\*\s*\n((?:\s*-[^\n]+\n?)+)', student_state)
        if m:
            lines = m.group(1).strip().split('\n')
            grade = ''; bg_parts = []
            for line in lines:
                line = line.strip('- ').strip()
                if '年级' in line: grade = line
                elif '奥数' in line or '经历' in line or '平均分' in line or '水平' in line or '编程' in line or '英语' in line or 'PET' in line or '目标' in line:
                    bg_parts.append(line)
            if grade or bg_parts:
                profile[course] = {"grade": grade, "background": '; '.join(bg_parts)}
                os.makedirs(os.path.dirname(profile_path), exist_ok=True)
                from utils import write_file
                write_file(profile_path, json.dumps(profile, ensure_ascii=False, indent=2))

    cp = profile.get(course, {})
    if cp.get("grade") or cp.get("background"):
        bg = f"\n## 学生背景（当前）\n**年级**: {cp.get('grade', '')}\n**背景**: {cp.get('background', '')}\n"
        student_state = bg + student_state
    world_model = _read_cached(f"courses/{course}/world_model.md")
    plan_rules = _read_cached(f"courses/{course}/planner.md")
    teacher_prompt = _read_cached(f"courses/{course}/teacher_prompt.md")

    return {
        "session_text": session_text,
        "compressed_mem": compressed_mem,
        "mem_context": related_sessions,
        "student_state": student_state,
        "world_model": world_model,
        "plan_rules": plan_rules,
        "teacher_prompt": teacher_prompt,
    }


class ChatRuntime:
    def __init__(self):
        pass

    def checkin(self, session_id: str, user_id: str, course: str = "math"):
        """Auto-checkin: when student opens the app, agent proactively greets
        and presents the current lesson plan."""
        mark_session_active(user_id, course, session_id)

        if not is_new_session(user_id, course):
            yield dict(type="text", content="欢迎回来！让我们继续上次的学习吧。")
            return

        # New session — send checkin prompt to LLM
        context = _build_context(user_id, course)
        mark_checkin_sent(user_id, course)

        checkin_prompt = f"""学生状态:
{context['student_state']}

排课规则:
{context['plan_rules']}

历史学习摘要（压缩记忆）:
{context['compressed_mem'] or '无'}

最近课堂内容:
{context['session_text'] or '这是学生的第一堂课。'}

========

学生刚刚打开学习系统。请你作为老师，主动向学生打招呼，简要回顾上节课的内容或当前学习进度，并告诉学生今天的学习计划是什么。保持亲切鼓励的语气，2-3 句话即可。"""

        messages = [
            {"role": "system", "content": f"learning world model:\n{context['world_model']}"},
            {"role": "user", "content": checkin_prompt}
        ]

        full_response = ""
        stream = llm.chat(messages, reasoning=True)
        for event in stream:
            content = event.choices[0].delta.content
            if content:
                yield dict(type="text", content=content)
                full_response += content

        if full_response:
            # Buffer greeting — flushed to session log only if student responds
            _pending_checkins[(user_id, course)] = full_response
            self._log(user_id, course, "[checkin]", full_response)

    def teach(self, session_id: str, user_input: str, user_id: str, course: str = "math"):
        """Stream a teaching response to the student."""

        mark_session_active(user_id, course, session_id)

        # Flush pending checkin greeting if student actually responds
        key = (user_id, course)
        if key in _pending_checkins:
            append_to_session(user_id, course, "assistant", _pending_checkins.pop(key), session_id)

        append_to_session(user_id, course, "user", user_input, session_id)
        memory.add(user_id, user_input)

        context = _build_context(user_id, course, user_input)
        full_response = ""

        try:
            messages = [
                {"role": "system", "content": f"""learning world model:
{context["world_model"]}"""},
                {"role": "user", "content": f"""学生状态:
{context['student_state']}

排课规则:
{context['plan_rules']}

历史学习摘要（压缩记忆）:
{context['compressed_mem'] or '无'}

最近的课堂记录:
{context['session_text'] or '这是第一堂课。'}

学生输入：
{user_input}"""}
            ]

            stream = llm.chat(messages, reasoning=True)
            for event in stream:
                content = event.choices[0].delta.content
                if content:
                    yield dict(type="text", content=content)
                    full_response += content

        finally:
            if full_response:
                append_to_session(user_id, course, "assistant", full_response, session_id)
            self._log(user_id, course, user_input, full_response)

    def eval(self, session_id: str, user_input: str, user_id: str, course: str = "math"):
        """Evaluate the student's response and update the student model."""
        context = _build_context(user_id, course, user_input)
        print("starting eval student status")

        response = llm.chat([
            {"role": "system", "content": f"""learning world model:
{context["world_model"]}"""},
            {"role": "user", "content": f"""学生状态:
{context['student_state']}

排课规则:
{context['plan_rules']}

历史学习摘要（压缩记忆）:
{context['compressed_mem'] or '无'}

最近的课堂记录:
{context['session_text'] or '这是第一堂课。'}

学生输入：
{user_input}

评估与规划:
{context["teacher_prompt"]}"""}
        ], stream=False, json=True, reasoning=True)

        try:
            eval_result = json.loads(response.choices[0].message.content)
            print(f"got eval result ", eval_result)
            model_update_delta = eval_result["model_update_delta"]
            eval_text = merge_to_text(eval_result)
            # Append plan as assistant message for context
            plan_text = format_teaching_plan(eval_result["teaching_plan"])
            append_to_session(user_id, course, "assistant",
                              f"[教学计划] {plan_text}", session_id)
            print("successfully create eval result: ", eval_text)
            if len(model_update_delta) > 0:
                delta_texts = []
                for i, d in enumerate(model_update_delta, 1):
                    delta_texts.append(f"{i}. {format_delta(d)}")
                state_update = "\n\n# DELTA UPDATE\n" + "\n".join(delta_texts)
                append_file(f"data/student/{user_id}/{course}_progress.md", state_update)
                print("receiving state updates: ", state_update)
            # Save to learning storage
            try:
                kps = extract_knowledge_points(eval_result)
                save_learning_record(user_id, course, session_id,
                                     eval_result.get('teaching_plan'),
                                     eval_result, kps)
            except Exception as e:
                print(f"storage save err: {e}")
        except json.JSONDecodeError as e:
            print(f"err decode:\n {response.choices[0].message.content}")

    def _log(self, user_id, course, user_input, response):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log = f"""
[{ts}]
COURSE: {course}

USER: {user_input}

TEACHER:
{response}
"""
        append_file(f"data/history/{user_id}_{course}.log", log)
