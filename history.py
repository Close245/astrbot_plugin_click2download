import json
import os
import time
from typing import Dict, Any

class HistoryManager:
    def __init__(self, base_dir: str):
        self.history_file = os.path.join(base_dir, "history.json")
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Gopeed History] 保存失败: {e}")

    def add_record(self, task_id: str, url: str, user_id: str, file_name: str = ""):
        """任务开始：记录基础信息"""
        self.data[task_id] = {
            "task_id": task_id,
            "url": url,
            "user_id": str(user_id),
            "file_name": file_name,
            "local_path": "",
            "size_bytes": 0,
            "start_ts": int(time.time()),
            "end_ts": 0,
            "deleted_ts": 0,
            "status": "downloading"
        }
        self._save()

    def update_completion(self, task_id: str, local_path: str, size_bytes: int):
        """任务完成：记录结束时间、路径和大小"""
        if task_id in self.data:
            self.data[task_id]["local_path"] = local_path
            self.data[task_id]["size_bytes"] = size_bytes
            self.data[task_id]["end_ts"] = int(time.time())
            self.data[task_id]["status"] = "completed"
            self._save()

    def mark_deleted(self, task_id: str):
        """文件删除：记录删除时间"""
        if task_id in self.data:
            self.data[task_id]["deleted_ts"] = int(time.time())
            self.data[task_id]["status"] = "deleted"
            self._save()

    def get_all_completed_tasks(self):
        """获取所有已完成且未删除的任务"""
        return {
            tid: info for tid, info in self.data.items() 
            if info["status"] == "completed" and info["deleted_ts"] == 0
        }