import json
import os
from typing import List, Optional, Dict
from datetime import datetime

DB_FILE = "tasks.json"

class Database:
    def __init__(self):
        self._ensure_db()

    def _ensure_db(self):
        if not os.path.exists(DB_FILE):
            with open(DB_FILE, "w") as f:
                json.dump([], f)

    def _read_data(self) -> List[Dict]:
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_data(self, data: List[Dict]):
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def add_task(self, task: Dict):
        data = self._read_data()
        # Insert at beginning
        data.insert(0, task)
        self._write_data(data)

    def update_task(self, task_id: str, updates: Dict):
        data = self._read_data()
        for task in data:
            if task["id"] == task_id:
                task.update(updates)
                break
        self._write_data(data)

    def get_tasks(self) -> List[Dict]:
        return self._read_data()

    def get_task(self, task_id: str) -> Optional[Dict]:
        data = self._read_data()
        for task in data:
            if task["id"] == task_id:
                return task
        return None

db = Database()

