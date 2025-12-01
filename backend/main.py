import os
import uuid
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from database import db
from worker import worker

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the worker loop
    asyncio.create_task(worker.start())
    yield
    # Shutdown logic if needed

app = FastAPI(title="Next Generate App Backend", lifespan=lifespan)

# ---------- 简单请求日志，中间件：记录客户端 IP 和时间 ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("request_logger")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    now = datetime.now().isoformat()

    logger.info(f"[REQUEST] {now} - {client_ip} {method} {path}")

    response = await call_next(request)

    return response

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated images statically
os.makedirs("generated_images", exist_ok=True)
app.mount("/images", StaticFiles(directory="generated_images"), name="images")

class GenerateRequest(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    steps: int = 20
    width: int = 512
    height: int = 512
    cfg_scale: float = 7.5

@app.post("/tasks")
async def create_task(request: GenerateRequest):
    task_id = str(uuid.uuid4())
    
    task = {
        "id": task_id,
        "prompt": request.prompt,
        "negative_prompt": request.negative_prompt,
        "status": "submitted",
        "created_at": datetime.now().isoformat(),
        "imageUrl": None
    }
    
    db.add_task(task)
    
    # Add to worker queue instead of BackgroundTasks
    # This ensures sequential processing and prevents server overload
    await worker.add_task(task_id, request.dict())
    
    return task

@app.get("/tasks")
async def get_tasks():
    return db.get_tasks()

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

if __name__ == "__main__":
    import uvicorn
    # Listen on all interfaces so emulator can access
    uvicorn.run(app, host="0.0.0.0", port=58732)
