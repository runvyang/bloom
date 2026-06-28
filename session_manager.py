import os
import json
from datetime import datetime

SESSION_DIR = "data/sessions"


class SessionManager:
    def __init__(self):
        os.makedirs(SESSION_DIR, exist_ok=True)

    def load(self, session_id):
        path = f"{SESSION_DIR}/{session_id}.json"

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

    def append(self, session_id, role, content):
        session = self.load(session_id)

        session["messages"].append({
            "role": role,
            "content": content,
            "time": str(datetime.now())
        })

        session["updated_at"] = str(datetime.now())

        self.save(session_id, session)

        return session

    def update_plan(self, session_id, plan, node=None):
        session = self.load(session_id)
        session["current_plan"] = plan
        self.save(session_id, session)

    def save(self, session_id, session):
        path = f"{SESSION_DIR}/{session_id}.json"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)
