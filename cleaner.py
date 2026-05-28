import asyncio
import os
import time
import stat  # 【新增】用于权限控制
from astrbot.api.all import logger
from .history import HistoryManager

class FileCleaner:
    def __init__(self, history_manager: HistoryManager):
        self.history = history_manager
        self.running = False

    async def start_loop(self, get_config_func):
        self.running = True
        logger.info("[Gopeed Cleaner] 自动清理服务已启动")
        
        while self.running:
            try:
                config = get_config_func()
                hours = config.auto_delete_hours
                
                if hours <= 0:
                    await asyncio.sleep(3600)
                    continue

                expiration_seconds = hours * 3600
                now = int(time.time())
                
                tasks = self.history.get_all_completed_tasks()
                
                for task_id, info in tasks.items():
                    end_ts = info.get("end_ts", 0)
                    local_path = info.get("local_path", "")
                    
                    if end_ts > 0 and (now - end_ts) > expiration_seconds:
                        self._perform_delete(task_id, local_path)

            except Exception as e:
                logger.error(f"[Gopeed Cleaner] 循环异常: {e}")
            
            await asyncio.sleep(600)

    def _perform_delete(self, task_id: str, path: str):
        if not path: return

        try:
            if os.path.exists(path):
                # 【跨平台修复】确保文件可写后再删除
                try:
                    os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)
                except Exception:
                    pass
                
                os.remove(path)
                logger.info(f"[Gopeed Cleaner] 已删除过期文件: {path}")
            
            self.history.mark_deleted(task_id)
        except Exception as e:
            logger.error(f"[Gopeed Cleaner] 删除失败 {path}: {e}")

    def stop(self):
        self.running = False