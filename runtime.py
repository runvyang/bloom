from llm import OpenRouterClient
from session_manager import SessionManager
from memory import MemoryManager
from utils import read_file, append_file, copy_file
from storage import save_learning_record, extract_knowledge_points, init_storage
from datetime import datetime
import json
import os
from fastapi import BackgroundTasks

llm = OpenRouterClient()
session_manager = SessionManager()
memory = MemoryManager()
init_storage()

from typing import List, Dict


def format_delta(delta: Dict) -> str:
    parts = [
        f"知识点：{delta['grade']}·{delta.get('module', '')}·{delta['knowledge_point']}（{delta['difficulty']}）",
        f"掌握度从“{delta['previous_mastery']}”变为“{delta['new_mastery']}”",
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
    # 处理 model_update_delta
    deltas = json_data.get('model_update_delta', [])
    if deltas:
        text_parts.append("【学生模型更新】")
        for i, d in enumerate(deltas, 1):
            text_parts.append(f"{i}. {format_delta(d)}")
    else:
        text_parts.append("【学生模型更新】本次无变化。")

    # 处理 teaching_plan
    plan = json_data.get('teaching_plan', {})
    if plan:
        text_parts.append("\n【教学计划】")
        text_parts.append(format_teaching_plan(plan))
    else:
        text_parts.append("\n【教学计划】无特别计划。")

    return "\n\n".join(text_parts)


class ChatRuntime:
    def __init__(self):
        pass

    def _prepare_context(self, session_id: str, user_input: str, user_id: str, course: str, log=True) -> dict:
        """
        准备所有上下文数据
        
        Returns:
            dict: 包含所有需要的上下文信息
        """
        # 1. session
        if log:
            session_manager.append(session_id, "user", user_input, user_id, course)
        session = session_manager.load(session_id, user_id)
        
        # 2. memory
        if log:
            memory.add(user_id, user_input)
        mem_context = memory.search(user_id, user_input)
        related_sessions = "\n".join([m['memory'] for m in mem_context["results"]])
        
        # 3. static files
        student_state_path = f"data/student/{user_id}/{course}_state.md"
        template_path = f"courses/{course}/student_state.md"
        if not os.path.exists(student_state_path):
            copy_file(template_path, student_state_path)
        student_state = read_file(student_state_path)
        world_model = read_file(f"courses/{course}/world_model.md")
        plan = read_file(f"courses/{course}/planner.md")
        teacher_prompt = read_file(f"courses/{course}/teacher_prompt.md")
        
        return {
            "session": session,
            "mem_context": related_sessions,
            "student_state": student_state,
            "user_input": user_input,
            "world_model": world_model,
            "plan": plan,
            "teacher_prompt": teacher_prompt
        }

    # 或者更清晰的方式
    def teach(self, session_id: str, user_input: str, user_id: str, course: str = "math"):
        """改进版本的chat方法"""
        # 1. 准备上下文
        context = self._prepare_context(session_id, user_input, user_id, course)
        full_response = ""
        
        try:
            messages = [
{"role": "system", "content": f"""
learning world model:
{context["world_model"]}
"""},

{"role": "user", "content": f"""
学生状态:
{context['student_state']}

排课计划:
{context["session"]["current_plan"]}

相关日志:
{context["mem_context"]}

课堂日志:
{context['session']['messages']}

学生输入：
{context['user_input']}
"""}
            ]
            stream = llm.chat(messages, reasoning=True)
            
            for event in stream:
                content = event.choices[0].delta.content
                if content:
                    yield dict(type="text", content=content)
                    full_response += content
            
        # 4. 更新 session
        finally:
            if full_response:
                session_manager.append(session_id, "assistant", full_response, user_id, course)
            self._log(session_id, user_input, full_response, user_id)

    def eval(self, session_id: str, user_input: str, user_id: str, course: str = "math"):
        # 1. 准备上下文
        context = self._prepare_context(session_id, user_input, user_id, course, log=False)
        print("starting eval student status")
        
        response = llm.chat([
            {"role": "system", "content": f"""
learning world model:
{context["world_model"]}
"""},
            {"role": "user", "content": f"""
学生状态:
{context['student_state']}

排课规则:
{context["plan"]}

之前的教学日志:
{context['mem_context']}

课堂日志:
{context['session']['messages']}

学生输入：
{context['user_input']}

评估与规划:
{context["teacher_prompt"]}
"""}
        ], stream=False, json=True, reasoning=True)

        try:
            eval_result = json.loads(response.choices[0].message.content)
            print(f"got eval result ", eval_result)
            model_update_delta = eval_result["model_update_delta"]
            eval_text = merge_to_text(eval_result)
            session_manager.update_plan(session_id, format_teaching_plan(eval_result["teaching_plan"]), user_id, course)
            print("successfully create eval result: ", eval_text)
            if len(model_update_delta) > 0:
                delta_texts = []
                for i, d in enumerate(model_update_delta, 1):
                    delta_texts.append(f"{i}. {format_delta(d)}")
                state_update = "\n\n# DELTA UPDATE\n" + "\n".join(delta_texts)
                append_file(f"data/student/{user_id}/{course}_state.md", state_update)
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
            

    def update_state(self, session_id: str, eval_result: str, user_input: str, user_id: str, course: str = "math"):
        context = self._prepare_context(session_id, user_input, user_id, course, log=False)

        response = llm.chat([
            {"role": "system", "content": f"""
learning world model:
{context["world_model"]}
"""},
            {"role": "user", "content": f"""
学生状态:
{context['student_state']}

新的评估
{eval_result}
"""}
        ], stream=False)


    def _log(self, session_id, user_input, response, user_id):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log = f"""
[{ts}]
SESSION: {session_id}

USER: {user_input}

TEACHER:
{response}
"""

        append_file(f"data/history/{user_id}.log", log)