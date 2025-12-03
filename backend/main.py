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
# 日志会追加写入 backend/server.log 文件（同时也会打印到控制台）
log_file_path = os.path.join(os.path.dirname(__file__), "server.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file_path, encoding="utf-8"),
    ],
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
    
    logger.info(f"Creating new task {task_id} with prompt: {request.prompt[:50]}...")
    
    task = {
        "id": task_id,
        "prompt": request.prompt,
        "negative_prompt": request.negative_prompt,
        "status": "submitted",
        "created_at": datetime.now().isoformat(),
        "imageUrl": None
    }
    
    try:
        db.add_task(task)
        logger.info(f"Task {task_id} saved to database")
    except Exception as e:
        logger.error(f"Failed to save task {task_id} to database: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save task: {str(e)}")
    
    # Ensure worker is running before adding task
    if not worker.is_running or (hasattr(worker, '_worker_task') and worker._worker_task and worker._worker_task.done()):
        logger.warning(f"Worker not running when task {task_id} created, attempting to restart...")
        try:
            await worker.start()
        except Exception as e:
            logger.error(f"Failed to start worker: {e}")
            raise HTTPException(status_code=500, detail=f"Worker is not available: {str(e)}")
    
    # Add to worker queue instead of BackgroundTasks
    # This ensures sequential processing and prevents server overload
    try:
        await worker.add_task(task_id, request.dict())
        logger.info(f"Task {task_id} added to worker queue successfully")
    except Exception as e:
        logger.error(f"Failed to add task {task_id} to queue: {e}")
        # Update task status to failed
        db.update_task(task_id, {"status": "failed", "error": f"Failed to queue task: {str(e)}"})
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")
    
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

@app.get("/health")
async def health_check():
    """Health check endpoint to verify worker status"""
    from engine import engine
    
    worker_status = {
        "is_running": worker.is_running,
        "queue_size": worker.queue.qsize(),
        "gpu_queue_size": worker.gpu_queue.qsize() if hasattr(worker, 'gpu_queue') else 0,
        "worker_task_alive": worker._worker_task is not None and not worker._worker_task.done() if hasattr(worker, '_worker_task') else False,
        "gpu_thread_alive": worker._gpu_thread is not None and worker._gpu_thread.is_alive() if hasattr(worker, '_gpu_thread') else False
    }
    
    model_status = {
        "is_ready": engine.is_ready(),
        "is_loading": engine.is_loading(),
        "error": engine.get_error()
    }
    
    # Check if worker is actually processing
    if not worker.is_running or (hasattr(worker, '_worker_task') and worker._worker_task and worker._worker_task.done()):
        logger.warning(f"Worker health check failed: {worker_status}")
        return {
            "status": "unhealthy",
            "worker": worker_status,
            "model": model_status,
            "message": "Worker is not running properly"
        }
    
    # Check if GPU thread is alive
    if hasattr(worker, '_gpu_thread') and (worker._gpu_thread is None or not worker._gpu_thread.is_alive()):
        logger.warning(f"GPU thread is not running: {worker_status}")
        return {
            "status": "unhealthy",
            "worker": worker_status,
            "model": model_status,
            "message": "GPU thread is not running"
        }
    
    return {
        "status": "healthy",
        "worker": worker_status,
        "model": model_status
    }

if __name__ == "__main__":
    import uvicorn
    # Listen on all interfaces so emulator can access
    uvicorn.run(app, host="0.0.0.0", port=58732)
