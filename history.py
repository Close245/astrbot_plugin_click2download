"""下载历史记录管理器 - 持久化到 JSON 文件"""
import json
import time
from pathlib import Path
from astrbot.api.all import logger


class HistoryManager:
    """管理所有下载任务的历史记录，支持增/改/查/标记删除"""

    def __init__(self, data_dir: Path):
        self.history_file = data_dir / "history.json"
        self._records: dict[str, dict] = {}
        self._load()

    # ---------- 内部持久化 ----------

    def _load(self):
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    self._records = json.load(f)
                logger.info(f"[Gopeed History] 已加载 {len(self._records)} 条历史记录")
            except Exception as e:
                logger.error(f"[Gopeed History] 加载历史记录失败: {e}")
                self._records = {}
        else:
            self._records = {}

    def _save(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[Gopeed History] 保存历史记录失败: {e}")

    # ---------- 对外接口 ----------

    def add_record(self, task_id: str, url: str, user_id: str, file_name: str):
        """新增一条下载记录（任务刚创建时调用）"""
        self._records[task_id] = {
            "url": url,
            "user_id": user_id,
            "file_name": file_name,
            "status": "pending",
            "local_path": "",
            "size_bytes": 0,
            "start_ts": int(time.time()),
            "end_ts": 0,
            "deleted": False,
        }
        self._save()
        logger.info(f"[Gopeed History] 新增记录: {task_id} -> {file_name}")

    def update_completion(self, task_id: str, local_path: str, size_bytes: int):
        """更新任务为已完成，记录本地路径和文件大小"""
        if task_id in self._records:
            rec = self._records[task_id]
            rec["status"] = "completed"
            rec["local_path"] = local_path
            rec["size_bytes"] = size_bytes
            if not rec.get("end_ts"):
                rec["end_ts"] = int(time.time())
            self._save()
            logger.info(f"[Gopeed History] 任务完成: {task_id}, 大小: {size_bytes} bytes")
        else:
            logger.warning(f"[Gopeed History] 尝试更新未知任务: {task_id}")

    def mark_deleted(self, task_id: str):
        """标记文件已被自动清理"""
        if task_id in self._records:
            self._records[task_id]["deleted"] = True
            self._save()
            logger.info(f"[Gopeed History] 已标记删除: {task_id}")

    def get_all_completed_tasks(self) -> dict[str, dict]:
        """返回所有已完成且尚未删除的任务（供清理器使用）"""
        return {
            tid: info
            for tid, info in self._records.items()
            if info.get("status") == "completed" and not info.get("deleted", False)
        }

    def get_record(self, task_id: str) -> dict | None:
        """获取单条记录"""
        return self._records.get(task_id)

    def get_all_records(self) -> dict[str, dict]:
        """返回全部记录（供展示或调试）"""
        return self._records
