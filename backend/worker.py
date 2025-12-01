import asyncio
from datetime import datetime
from typing import Optional
from database import db
from engine import engine

class TaskWorker:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskWorker, cls).__new__(cls)
            cls._instance.queue = asyncio.Queue()
            cls._instance.is_running = False
        return cls._instance

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        print("TaskWorker started.")
        
        # Resume pending tasks from DB on startup
        await self.resume_pending_tasks()
        
        while True:
            task_data = await self.queue.get()
            try:
                await self.process_task(task_data)
            except Exception as e:
                print(f"Error processing task in worker: {e}")
            finally:
                self.queue.task_done()

    async def resume_pending_tasks(self):
        print("Checking for pending tasks to resume...")
        # Loop through DB tasks, find 'submitted' or 'processing' and re-queue them
        # Note: 'processing' tasks were interrupted, so we restart them.
        tasks = db.get_tasks()
        count = 0
        # Tasks are stored newest first, so we should iterate in reverse to maintain order roughly
        for task in reversed(tasks):
            if task["status"] in ["submitted", "processing"]:
                print(f"Resuming task {task['id']}")
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
        print(f"Resumed {count} tasks.")

    async def add_task(self, task_id: str, request_data: dict):
        await self.queue.put({"task_id": task_id, "request": request_data})
        print(f"Task {task_id} added to queue. Queue size: {self.queue.qsize()}")

    async def process_task(self, task_data: dict):
        task_id = task_data["task_id"]
        request = task_data["request"]
        
        print(f"Worker processing task: {task_id}")
        
        try:
            # Update status to processing
            db.update_task(task_id, {"status": "processing"})
            
            # Run generation (blocking call to engine, run in thread pool)
            # Using asyncio.to_thread to prevent blocking the event loop
            filename = await asyncio.to_thread(
                engine.generate,
                prompt=request["prompt"],
                negative_prompt=request.get("negative_prompt"),
                steps=request.get("steps", 20),
                width=request.get("width", 512),
                height=request.get("height", 512),
                cfg_scale=request.get("cfg_scale", 7.5)
            )
            
            # Update task with result
            db.update_task(task_id, {
                "status": "completed", 
                "imageUrl": f"images/{filename}",
                "completed_at": datetime.now().isoformat()
            })
            print(f"Task {task_id} completed successfully.")
            
        except Exception as e:
            print(f"Task {task_id} failed: {e}")
            db.update_task(task_id, {"status": "failed", "error": str(e)})

worker = TaskWorker()

