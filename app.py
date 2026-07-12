from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import BackgroundTasks
from pydantic import BaseModel
from runtime import ChatRuntime
from auth import init_db, register_user, authenticate_user, validate_session, invalidate_session
from auth import admin_login, validate_admin, admin_logout, list_users
from auth import get_user_states, get_user_state_content, list_user_sessions, get_user_session_content
from auth import list_unified_sessions, get_unified_session_content, reset_user_password
import json
import os

app = FastAPI(title="智能教学助手API", version="1.0.0")

# Voice WebSocket route
from voice_ws import handle_voice

from fastapi import WebSocket

@app.websocket("/ws/voice/oral_english")
async def ws_voice(ws: WebSocket):
    await ws.accept()
    await handle_voice(ws)

# 初始化
chat_runtime = ChatRuntime()
init_db()

# =========================
# 静态文件服务
# =========================
# 确保static目录存在
os.makedirs("static", exist_ok=True)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# =========================
# 根路径 - 返回前端页面
# =========================
@app.get("/")
def root():
    """返回前端UI页面"""
    return FileResponse("static/index.html")

@app.get("/admin")
def admin_page():
    """返回Admin管理页面"""
    return FileResponse("static/admin.html")

@app.get("/oral-english")
def oral_english_page():
    """返回英语口语练习页面"""
    return FileResponse("static/oral_english.html")

# =========================
# Auth dependency
# =========================
def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    user = validate_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user

# =========================
# AUTH API
# =========================
class AuthRegisterReq(BaseModel):
    username: str
    password: str

@app.post("/auth/register")
def auth_register(req: AuthRegisterReq):
    result = register_user(req.username, req.password)
    if not result["success"]:
        raise HTTPException(status_code=409, detail=result["error"])
    return result

class AuthLoginReq(BaseModel):
    username: str
    password: str

@app.post("/auth/login")
def auth_login(req: AuthLoginReq):
    result = authenticate_user(req.username, req.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    return result

@app.post("/auth/logout")
def auth_logout(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    invalidate_session(token)
    return {"success": True}

@app.get("/auth/me")
def auth_me(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    user = validate_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"success": True, "user": user}

# =========================
# ADMIN API
# =========================
class AdminLoginReq(BaseModel):
    password: str

@app.post("/admin/login")
def admin_login_route(req: AdminLoginReq):
    result = admin_login(req.password)
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    return result

def get_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    if not validate_admin(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True

@app.get("/admin/users")
def admin_list_users(admin: bool = Depends(get_admin)):
    return {"users": list_users()}

@app.get("/admin/state/{username}")
def admin_get_states(username: str, admin: bool = Depends(get_admin)):
    return {"states": get_user_states(username)}

@app.get("/admin/state/{username}/{course}")
def admin_get_state_content(username: str, course: str, admin: bool = Depends(get_admin)):
    content = get_user_state_content(username, course)
    if content is None:
        raise HTTPException(status_code=404, detail="State file not found")
    return {"content": content, "course": course, "username": username}

@app.get("/admin/sessions/{username}")
def admin_list_user_sessions(username: str, admin: bool = Depends(get_admin)):
    return {"sessions": list_user_sessions(username)}

@app.get("/admin/session/{username}/{session_id}")
def admin_get_session(username: str, session_id: str, admin: bool = Depends(get_admin)):
    content = get_user_session_content(username, session_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session": content, "username": username}

@app.get("/admin/unified-sessions/{username}")
def admin_list_unified_sessions(username: str, admin: bool = Depends(get_admin)):
    return {"sessions": list_unified_sessions(username)}

@app.get("/admin/unified-session/{username}/{course}")
def admin_get_unified_session(username: str, course: str, admin: bool = Depends(get_admin)):
    messages = get_unified_session_content(username, course)
    return {"messages": messages, "course": course, "username": username}

class ResetPasswordReq(BaseModel):
    username: str
    new_password: str

@app.post("/admin/reset-password")
def admin_reset_password(req: ResetPasswordReq, admin: bool = Depends(get_admin)):
    result = reset_user_password(req.username, req.new_password)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

# =========================
# TASK & CALENDAR API
# =========================
from storage import (generate_daily_tasks, get_daily_tasks, start_task,
                     complete_task, heartbeat_task, get_streak_info,
                     get_calendar, get_daily_detail, get_recent_records)

class TaskStartReq(BaseModel):
    course: str
    session_id: str = ""

@app.get("/tasks/today")
def api_daily_tasks(user: dict = Depends(get_current_user)):
    tasks = generate_daily_tasks(user["username"])
    streak = get_streak_info(user["username"])
    return {"tasks": tasks, "streak": streak}

@app.post("/tasks/start")
def api_start_task(req: TaskStartReq, user: dict = Depends(get_current_user)):
    tasks = start_task(user["username"], req.course, req.session_id)
    return {"tasks": tasks}

@app.post("/tasks/heartbeat")
def api_heartbeat(req: TaskStartReq, user: dict = Depends(get_current_user)):
    return heartbeat_task(user["username"], req.course)

@app.post("/tasks/complete")
def api_complete_task(req: TaskStartReq, user: dict = Depends(get_current_user)):
    tasks = complete_task(user["username"], req.course)
    return {"tasks": tasks}

@app.get("/tasks/streak")
def api_streak(user: dict = Depends(get_current_user)):
    return get_streak_info(user["username"])

@app.get("/tasks/calendar")
def api_calendar(year: int = 0, month: int = 0, user: dict = Depends(get_current_user)):
    from datetime import date
    if not year:
        year = date.today().year
    if not month:
        month = date.today().month
    return {"days": get_calendar(user["username"], year, month), "year": year, "month": month}

@app.get("/tasks/detail/{target_date}")
def api_daily_detail(target_date: str, user: dict = Depends(get_current_user)):
    return get_daily_detail(user["username"], target_date)

@app.get("/tasks/records")
def api_records(course: str = "", user: dict = Depends(get_current_user)):
    records = get_recent_records(user["username"], course if course else None, limit=20)
    return {"records": records}

# =========================
# CHECKIN API — proactive greeting
# =========================
class CheckinReq(BaseModel):
    session_id: str
    course: str = "math"

@app.post("/checkin")
def api_checkin(req: CheckinReq, user: dict = Depends(get_current_user)):
    def generate():
        for chunk in chat_runtime.checkin(req.session_id, user["username"], req.course):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

# =========================
# CHAT API（实时教学）
# =========================
class ChatReq(BaseModel):
    session_id: str
    message: str
    course: str = "math"

@app.post("/chat/stream")
def chat(req: ChatReq, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    user_id = user["username"]

    def generate():
        for chunk in chat_runtime.teach(req.session_id, req.message, user_id, req.course):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    background_tasks.add_task(chat_runtime.eval, req.session_id, req.message, user_id, req.course)
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# =========================
# 健康检查
# =========================
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "智能教学助手"
    }

# =========================
# 启动配置
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )