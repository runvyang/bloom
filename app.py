from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import BackgroundTasks
from pydantic import BaseModel
from runtime import ChatRuntime
import json
import os

app = FastAPI(title="智能教学助手API", version="1.0.0")

# 初始化
chat_runtime = ChatRuntime()

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
# CHAT API（实时教学）
# =========================
class ChatReq(BaseModel):
    session_id: str
    message: str

@app.post("/chat/stream")
def chat(req: ChatReq, background_tasks: BackgroundTasks):
    def generate():
        for chunk in chat_runtime.teach(req.session_id, req.message):
            yield f"data: {json.dumps(chunk)}\n\n"
        yield "data: [DONE]\n\n"

    background_tasks.add_task(chat_runtime.eval, req.session_id, req.message)
    
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