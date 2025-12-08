import asyncio
import os
import time
from .history import HistoryManager

class FileCleaner:
    def __init__(self, history_manager: HistoryManager, logger):
        self.history = history_manager
        self.logger = logger
        self.running = False

    async def start_loop(self, get_config_func):
        """启动清理循环"""
        self.running = True
        self.logger.info("[Gopeed Cleaner] 自动清理服务已启动")
        
        while self.running:
            try:
                # 获取最新配置
                config = get_config_func()
                hours = config.auto_delete_hours
                
                # 如果设置为 0，则不删除，直接休眠
                if hours <= 0:
                    await asyncio.sleep(3600) # 休眠1小时
                    continue

                # 转换小时为秒
                expiration_seconds = hours * 3600
                now = int(time.time())
                
                # 获取所有待检查的任务
                tasks = self.history.get_all_completed_tasks()
                
                for task_id, info in tasks.items():
                    end_ts = info.get("end_ts", 0)
                    local_path = info.get("local_path", "")
                    
                    # 检查是否过期
                    if end_ts > 0 and (now - end_ts) > expiration_seconds:
                        self._perform_delete(task_id, local_path)

            except Exception as e:
                self.logger.error(f"[Gopeed Cleaner] 循环异常: {e}")
            
            # 每 10 分钟检查一次
            await asyncio.sleep(600)

    def _perform_delete(self, task_id: str, path: str):
        """执行删除操作"""
        if not path: 
            return

        try:
            if os.path.exists(path):
                os.remove(path)
                self.logger.info(f"[Gopeed Cleaner] 已自动删除过期文件: {path}")
            else:
                # 文件已经不见了
                pass
            
            # 无论文件是否真的存在（可能被手动删了），都标记为已删除
            self.history.mark_deleted(task_id)
            
        except Exception as e:
            self.logger.error(f"[Gopeed Cleaner] 删除文件失败 {path}: {e}")

    def stop(self):
        self.running = False