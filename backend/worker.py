import asyncio
import traceback
import threading
import queue
from datetime import datetime, timedelta
from typing import Optional
from database import db
from engine import engine

class TaskWorker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskWorker, cls).__new__(cls)
            cls._instance.queue = asyncio.Queue()  # 异步队列：接收任务
            cls._instance.gpu_queue = queue.Queue()  # 同步队列：GPU线程消费
            cls._instance.is_running = False
            cls._instance._worker_task = None
            cls._instance._model_loading_task = None
            cls._instance._gpu_thread = None
            cls._instance._gpu_thread_stop = threading.Event()
        return cls._instance

    async def start(self):
        if self.is_running and self._worker_task and not self._worker_task.done():
            print("[Worker] TaskWorker already running.")
            return
        
        # Reset state if previous worker died
        if self._worker_task and self._worker_task.done():
            print("[Worker] Previous worker task ended, restarting...")
            self.is_running = False
        
        self.is_running = True
        print("[Worker] TaskWorker started.")
        
        # Start model loading in background thread if not already loaded/loading
        if not engine.is_ready() and not engine.is_loading():
            print("[Worker] Starting model loading in background thread...")
            self._model_loading_task = asyncio.create_task(self._load_model_async())
        elif engine.is_loading():
            print("[Worker] Model is already loading, waiting for completion...")
        elif engine.is_ready():
            print("[Worker] Model is already loaded and ready.")
        
        # Start GPU processing thread (专门处理GPU任务的线程)
        if self._gpu_thread is None or not self._gpu_thread.is_alive():
            print("[Worker] Starting GPU processing thread...")
            self._gpu_thread_stop.clear()
            self._gpu_thread = threading.Thread(
                target=self._gpu_worker_thread,
                name="GPUWorkerThread",
                daemon=True
            )
            self._gpu_thread.start()
            print("[Worker] GPU processing thread started.")
        
        # Resume pending tasks from DB on startup
        try:
            await self.resume_pending_tasks()
        except Exception as e:
            print(f"[Worker] Error resuming pending tasks: {e}")
            traceback.print_exc()
        
        # Start worker loop in background task
        self._worker_task = asyncio.create_task(self._worker_loop())
    
    async def _load_model_async(self):
        """在后台线程中异步加载模型"""
        try:
            print("[Worker] Loading model in background thread...")
            # 使用 asyncio.to_thread 在后台线程中执行同步的 load_model
            await asyncio.to_thread(engine.load_model)
            print("[Worker] Model loaded successfully in background thread.")
        except Exception as e:
            print(f"[Worker] Failed to load model in background thread: {e}")
            traceback.print_exc()
        
    async def _worker_loop(self):
        """Main worker loop with robust error handling"""
        retry_count = 0
        max_retries = 5
        model_wait_count = 0
        
        while self.is_running:
            try:
                # Check if model is ready before processing tasks
                if not engine.is_ready():
                    if engine.is_loading():
                        # Model is loading, wait a bit and check queue (don't block forever)
                        model_wait_count += 1
                        if model_wait_count % 10 == 0:  # Log every 10 seconds
                            print(f"[Worker] Waiting for model to load... (checked {model_wait_count} times)")
                    elif engine.get_error():
                        # Model loading failed
                        error_msg = engine.get_error()
                        print(f"[Worker] Model loading failed: {error_msg}")
                        # Still try to get tasks from queue to mark them as failed
                        # But we'll handle this in process_task
                    else:
                        # Model not started loading yet, wait a bit
                        await asyncio.sleep(0.5)
                        continue
                
                # Wait for task with timeout to allow periodic health checks
                try:
                    task_data = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Timeout is normal, just continue the loop
                    continue
                
                # Reset model wait count when we get a task
                model_wait_count = 0
                
                try:
                    await self.process_task(task_data)
                except Exception as e:
                    print(f"[Worker] Error processing task in worker: {e}")
                    traceback.print_exc()
                finally:
                    self.queue.task_done()
                    retry_count = 0  # Reset retry count on successful task processing
                    
            except Exception as e:
                print(f"[Worker] Critical error in worker loop: {e}")
                traceback.print_exc()
                retry_count += 1
                
                if retry_count >= max_retries:
                    print(f"[Worker] Worker loop failed {max_retries} times, stopping worker.")
                    self.is_running = False
                    break
                
                # Exponential backoff before retry
                await asyncio.sleep(min(2 ** retry_count, 60))
        
        print("[Worker] Worker loop exited.")

    async def resume_pending_tasks(self):
        print("[Worker] Checking for pending tasks to resume...")
        # Loop through DB tasks, find 'submitted' or 'processing' and re-queue them
        # Note: 'processing' tasks were interrupted, so we restart them.
        tasks = db.get_tasks()
        count = 0
        stuck_count = 0
        
        # Check for stuck processing tasks (older than 10 minutes)
        cutoff_time = datetime.now() - timedelta(minutes=10)
        
        # Tasks are stored newest first, so we should iterate in reverse to maintain order roughly
        for task in reversed(tasks):
            if task["status"] == "processing":
                # Check if task is stuck (processing for too long)
                created_at_str = task.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                        if created_at < cutoff_time:
                            print(f"[Worker] Found stuck processing task {task['id']}, resetting to submitted")
                            db.update_task(task["id"], {"status": "submitted"})
                            stuck_count += 1
                    except (ValueError, TypeError):
                        pass
            
            if task["status"] in ["submitted", "processing"]:
                print(f"[Worker] Resuming task {task['id']} (status: {task['status']})")
                # We need to reconstruct the request data. 
                # The current DB stores prompt etc at top level, so it maps easily.
                request_data = {
                    "prompt": task["prompt"],
                    "negative_prompt": task.get("negative_prompt"),
                    # We didn't store these params in DB task object in main.py create_task!
                    # FIX: We need to be able to resume. 
                    # For now, let's use defaults if missing, OR update main.py to store them.
                    # Assuming defaults for now to keep it simple, or extracting if present.
                    "steps": 20, "width": 512, "height": 512, "cfg_scale": 7.5
                }
                await self.queue.put({"task_id": task["id"], "request": request_data})
                count += 1
        
        if stuck_count > 0:
            print(f"[Worker] Reset {stuck_count} stuck processing tasks to submitted status")
        print(f"[Worker] Resumed {count} tasks.")

    async def add_task(self, task_id: str, request_data: dict):
        # Ensure worker is running before adding task
        if not self.is_running or (self._worker_task and self._worker_task.done()):
            print("[Worker] Worker not running, attempting to restart...")
            await self.start()
        
        await self.queue.put({"task_id": task_id, "request": request_data})
        queue_size = self.queue.qsize()
        print(f"[Worker] Task {task_id} added to queue. Queue size: {queue_size}")
        
        # Log warning if queue is getting large
        if queue_size > 10:
            print(f"[Worker] WARNING: Queue size is {queue_size}, consider scaling or checking worker performance")

    def _gpu_worker_thread(self):
        """专门处理GPU任务的线程，串行执行任务"""
        print("[GPUThread] GPU worker thread started, waiting for tasks...")
        
        while not self._gpu_thread_stop.is_set():
            try:
                # 从同步队列中获取任务，超时1秒以便检查停止信号
                try:
                    gpu_task = self.gpu_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                task_id = gpu_task["task_id"]
                request = gpu_task["request"]
                future = gpu_task["future"]  # asyncio.Future，用于返回结果
                
                print(f"[GPUThread] Processing GPU task: {task_id}, prompt: {request.get('prompt', '')[:50]}...")
                
                try:
                    # 检查模型是否就绪
                    if not engine.is_ready():
                        if engine.is_loading():
                            error_msg = "模型正在加载中，请稍候再试"
                        elif engine.get_error():
                            error_msg = f"模型加载失败: {engine.get_error()}"
                        else:
                            error_msg = "模型未就绪"
                        
                        print(f"[GPUThread] {error_msg}")
                        # 通过 future 返回错误
                        if future and not future.done():
                            future.set_exception(RuntimeError(error_msg))
                        continue
                    
                    # 执行GPU任务（同步调用，在这个线程中串行执行）
                    filename = engine.generate(
                        prompt=request["prompt"],
                        negative_prompt=request.get("negative_prompt"),
                        steps=request.get("steps", 20),
                        width=request.get("width", 512),
                        height=request.get("height", 512),
                        cfg_scale=request.get("cfg_scale", 7.5)
                    )
                    
                    print(f"[GPUThread] Task {task_id} completed. Image: {filename}")
                    # 通过 future 返回结果
                    if future and not future.done():
                        future.set_result(filename)
                    
                except Exception as e:
                    error_msg = str(e)
                    print(f"[GPUThread] Task {task_id} failed: {error_msg}")
                    traceback.print_exc()
                    # 通过 future 返回异常
                    if future and not future.done():
                        future.set_exception(e)
                
                finally:
                    self.gpu_queue.task_done()
                    
            except Exception as e:
                # 处理外层循环的异常（比如队列操作异常等）
                print(f"[GPUThread] Critical error in GPU worker thread: {e}")
                traceback.print_exc()
                # 继续循环，不退出线程
        
        print("[GPUThread] GPU worker thread stopped.")

    async def process_task(self, task_data: dict):
        task_id = task_data["task_id"]
        request = task_data["request"]
        
        print(f"[Worker] Processing task: {task_id}, prompt: {request.get('prompt', '')[:50]}...")
        
        try:
            # Check if model is ready before processing
            if not engine.is_ready():
                if engine.is_loading():
                    error_msg = "模型正在加载中，请稍候再试"
                    print(f"[Worker] {error_msg}")
                    db.update_task(task_id, {
                        "status": "failed",
                        "error": error_msg,
                        "failed_at": datetime.now().isoformat()
                    })
                    return
                elif engine.get_error():
                    error_msg = f"模型加载失败: {engine.get_error()}"
                    print(f"[Worker] {error_msg}")
                    db.update_task(task_id, {
                        "status": "failed",
                        "error": error_msg,
                        "failed_at": datetime.now().isoformat()
                    })
                    return
                else:
                    error_msg = "模型未就绪"
                    print(f"[Worker] {error_msg}")
                    db.update_task(task_id, {
                        "status": "failed",
                        "error": error_msg,
                        "failed_at": datetime.now().isoformat()
                    })
                    return
            
            # Update status to processing
            db.update_task(task_id, {"status": "processing"})
            print(f"[Worker] Task {task_id} status updated to processing, queued to GPU thread")
            
            # 创建 Future 用于接收 GPU 线程的结果
            future = asyncio.Future()
            
            # 将任务放入 GPU 队列（同步队列）
            self.gpu_queue.put({
                "task_id": task_id,
                "request": request,
                "future": future
            })
            
            # 等待 GPU 线程完成（带超时）
            timeout_seconds = 300  # 5 minutes timeout
            try:
                filename = await asyncio.wait_for(future, timeout=timeout_seconds)
                
                # Update task with result
                db.update_task(task_id, {
                    "status": "completed", 
                    "imageUrl": f"images/{filename}",
                    "completed_at": datetime.now().isoformat()
                })
                print(f"[Worker] Task {task_id} completed successfully. Image: {filename}")
                
            except asyncio.TimeoutError:
                error_msg = f"Task {task_id} timed out after {timeout_seconds} seconds"
                print(f"[Worker] {error_msg}")
                db.update_task(task_id, {
                    "status": "failed", 
                    "error": error_msg,
                    "failed_at": datetime.now().isoformat()
                })
                raise
            except Exception as e:
                # GPU 线程返回的异常
                error_msg = str(e)
                print(f"[Worker] Task {task_id} failed: {error_msg}")
                db.update_task(task_id, {
                    "status": "failed", 
                    "error": error_msg,
                    "failed_at": datetime.now().isoformat()
                })
                raise
            
        except Exception as e:
            error_msg = str(e)
            print(f"[Worker] Task {task_id} failed: {error_msg}")
            traceback.print_exc()
            try:
                db.update_task(task_id, {
                    "status": "failed", 
                    "error": error_msg,
                    "failed_at": datetime.now().isoformat()
                })
            except Exception as db_error:
                print(f"[Worker] Failed to update task status in DB: {db_error}")

worker = TaskWorker()

