from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import BackgroundTasks
from pydantic import BaseModel
from runtime import ChatRuntime
from auth import init_db, register_user, authenticate_user, validate_session, invalidate_session
import json
import os

app = FastAPI(title="智能教学助手API", version="1.0.0")

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
# CHAT API（实时教学）
# =========================
class ChatReq(BaseModel):
    session_id: str
    message: str

@app.post("/chat/stream")
def chat(req: ChatReq, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    user_id = user["username"]

    def generate():
        for chunk in chat_runtime.teach(req.session_id, req.message, user_id):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    background_tasks.add_task(chat_runtime.eval, req.session_id, req.message, user_id)
    
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