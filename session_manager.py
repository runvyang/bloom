import os
import json
from datetime import datetime


def _session_dir(user_id: str) -> str:
    return f"data/student/{user_id}/sessions"


class SessionManager:
    def load(self, session_id: str, user_id: str):
        session_dir = _session_dir(user_id)
        path = f"{session_dir}/{session_id}.json"

        if not os.path.exists(path):
            return {
                "session_id": session_id,
                "messages": [],
                "current_plan": None,
                "created_at": str(datetime.now()),
                "updated_at": str(datetime.now())
            }

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def append(self, session_id: str, role: str, content: str, user_id: str, course: str = ""):
        session = self.load(session_id, user_id)

        session["messages"].append({
            "role": role,
            "content": content,
            "time": str(datetime.now())
        })

        session["updated_at"] = str(datetime.now())
        if course and not session.get("course"):
            session["course"] = course

        self.save(session_id, user_id, session)

        return session

    def update_plan(self, session_id: str, plan: str, user_id: str, course: str = "", node=None):
        session = self.load(session_id, user_id)
        session["current_plan"] = plan
        if course and not session.get("course"):
            session["course"] = course
        self.save(session_id, user_id, session)

    def save(self, session_id: str, user_id: str, session: dict):
        session_dir = _session_dir(user_id)
        path = f"{session_dir}/{session_id}.json"

        os.makedirs(session_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)
