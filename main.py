from astrbot.api.all import *
from astrbot.api.event import filter
from astrbot.api.message_components import Plain
from astrbot.api.star import StarTools
from pydantic import BaseModel
from aiohttp import web
import aiohttp
import asyncio
import json
import os
import time
import re
import html
from pathlib import Path
from urllib.parse import unquote

# 导入子模块
from .history import HistoryManager
from .cleaner import FileCleaner

# ================= 配置模型 =================
class GopeedConfig(BaseModel):
    gopeed_host: str = "http://127.0.0.1:9999"
    api_token: str = ""
    download_path: str = ""
    upload_size_limit_mb: int = 500
    remote_path_prefix: str = ""
    local_path_prefix: str = ""
    napcat_path_prefix: str = "" # NapCat 路径映射
    auto_download_mode: bool = False
    webhook_server_port: int = 0 
    auto_delete_hours: int = 24

# ================= 插件主逻辑 =================
@register("astrbot_plugin_click2download", "YourName", "Gopeed 下载助手", "3.6.0", "规范化重构版")
class GopeedPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        
        # 1. 【规范修复】使用 StarTools 获取标准数据目录
        # 路径通常为: data/plugin_data/astrbot_plugin_click2download/
        self.data_dir = StarTools.get_data_dir("astrbot_plugin_click2download")
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[Gopeed] 数据目录已初始化: {self.data_dir}")

        self.tasks_record_path = self.data_dir / "context_map.json"
        
        self.server_runner = None
        self.cached_bot = None
        
        # 2. 【规范修复】配置加载
        # 不再回写 config.json 到源码目录，避免污染环境
        if config:
            self.config = GopeedConfig(**config)
        else:
            self.config = GopeedConfig()
            logger.warning("[Gopeed] 未检测到注入配置，使用默认值")

        # 3. 模块初始化
        self.history = HistoryManager(self.data_dir)
        self.cleaner = FileCleaner(self.history)
        
        asyncio.create_task(self.cleaner.start_loop(self._get_current_config))
        self.tasks_context_map = self._load_context_map()

        if self.config.webhook_server_port > 0:
            asyncio.create_task(self._start_webhook_server())
        else:
            logger.critical("[Gopeed] ❌ 错误: Webhook端口未配置! 插件无法接收通知。")

    # 【规范修复】使用 terminate 钩子替代 __del__ 进行资源清理
    async def terminate(self):
        logger.info("[Gopeed] 正在停止服务...")
        if self.server_runner:
            await self.server_runner.cleanup()
        if hasattr(self, 'cleaner'):
            self.cleaner.stop()

    # --- 辅助方法 ---
    def _get_bot(self):
        if self.cached_bot: return self.cached_bot
        try:
            if hasattr(self.context, "platform_manager"):
                for platform in self.context.platform_manager.platforms.values():
                    if hasattr(platform, "bots") and platform.bots:
                        for bot in platform.bots.values():
                            self.cached_bot = bot
                            return bot
        except: pass
        return None

    def _get_current_config(self) -> GopeedConfig:
        return self.config

    # --- 上下文管理 ---
    def _load_context_map(self) -> dict:
        if self.tasks_record_path.exists():
            try:
                with open(self.tasks_record_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[Gopeed] 读取上下文失败: {e}")
                return {}
        return {}

    def _save_context_map(self):
        try:
            with open(self.tasks_record_path, "w", encoding="utf-8") as f:
                json.dump(self.tasks_context_map, f, indent=4)
        except Exception as e:
            logger.error(f"[Gopeed] 保存上下文失败: {e}")

    def _register_context(self, task_id: str, event: AstrMessageEvent):
        if not task_id: return
        if hasattr(event, "bot"): self.cached_bot = event.bot

        msg_obj = event.message_obj
        target_type = "private"
        target_id = event.get_sender_id()
        
        if hasattr(msg_obj, "group_id") and msg_obj.group_id:
            target_type = "group"
            target_id = msg_obj.group_id
        
        safe_id = str(task_id).strip()
        self.tasks_context_map[safe_id] = {
            "type": target_type,
            "id": target_id,
            "timestamp": int(time.time())
        }
        self._save_context_map()
        logger.info(f"[Gopeed] 任务注册: {safe_id} -> {target_type}:{target_id}")

    def _remove_context(self, task_id):
        safe_id = str(task_id).strip()
        if safe_id in self.tasks_context_map:
            del self.tasks_context_map[safe_id]
            self._save_context_map()

    # --- Webhook 服务 ---
    async def _start_webhook_server(self):
        app = web.Application()
        app.router.add_post('/webhook', self._handle_webhook_request)
        app.router.add_get('/webhook', self._handle_webhook_test)
        
        self.server_runner = web.AppRunner(app)
        await self.server_runner.setup()
        
        port = self.config.webhook_server_port
        try:
            site = web.TCPSite(self.server_runner, '0.0.0.0', port)
            await site.start()
            logger.info(f"[Gopeed] Webhook 服务启动: 0.0.0.0:{port}")
        except Exception as e:
            logger.error(f"[Gopeed] Webhook 启动失败: {e}")

    async def _handle_webhook_test(self, request):
        return web.Response(text="Gopeed Bot Webhook OK", status=200)

    async def _handle_webhook_request(self, request):
        try:
            try:
                data = await request.json()
            except:
                return web.Response(text="OK", status=200)

            event_type = data.get("event", "UNKNOWN")
            payload_data = data.get("payload", {})
            task_info = payload_data.get("task", {})
            raw_id = task_info.get("id") or data.get("task_id")
            
            if not raw_id:
                return web.Response(text="OK", status=200)
            
            task_id = str(raw_id).strip()

            max_wait_retries = 10 
            found_context = False
            
            for i in range(max_wait_retries):
                if task_id in self.tasks_context_map:
                    found_context = True
                    break
                if i % 2 == 0:
                    logger.warning(f"[Gopeed] 等待上下文同步 ({i+1}/{max_wait_retries})... ID: {task_id}")
                await asyncio.sleep(1)

            if not found_context:
                logger.error(f"[Gopeed] 放弃处理未知任务: {task_id}")
                return web.Response(text="Ignored", status=200)

            task_context = self.tasks_context_map[task_id]
            opts = task_info.get("meta", {}).get("opts", {})
            file_name = opts.get("name", "未知文件")

            if event_type == "DOWNLOAD_START":
                await self._send_text_msg(task_context, f"▶️ 开始下载: {file_name}")
            elif event_type == "DOWNLOAD_FAILED":
                err = task_info.get("error", "未知错误")
                await self._send_text_msg(task_context, f"❌ 下载失败: {file_name}\n原因: {err}")
                self._remove_context(task_id)
            elif event_type == "DOWNLOAD_DONE":
                remote_dir = opts.get("path")
                res = task_info.get("meta", {}).get("res", {})
                file_size_bytes = res.get("size", 0)
                
                logger.info(f"[Gopeed] 下载完成: {file_name}")
                asyncio.create_task(self._process_download_done(task_context, task_id, remote_dir, file_name, file_size_bytes))
            
            return web.Response(text="Processing", status=200)

        except Exception as e:
            logger.error(f"[Gopeed] Webhook Error: {e}")
            return web.Response(text="Error", status=500)

    # --- 任务完成与上传 ---
    async def _process_download_done(self, task_context: dict, task_id: str, remote_dir: str, file_name: str, file_size_bytes: int):
        config = self._get_current_config()

        if remote_dir.endswith("/") or remote_dir.endswith("\\"):
            remote_full_path = f"{remote_dir}{file_name}"
        else:
            remote_full_path = f"{remote_dir}/{file_name}"

        local_path = self._map_path(remote_full_path, config)
        await asyncio.sleep(1) 

        if not os.path.exists(local_path):
            await self._send_text_msg(task_context, f"❌ 文件丢失。\nBot路径: {local_path}\n请检查路径映射。")
            self._remove_context(task_id)
            return

        self.history.update_completion(task_id, local_path, file_size_bytes)

        file_size_mb = file_size_bytes / (1024 * 1024)
        limit_mb = config.upload_size_limit_mb
        
        if file_size_mb > limit_mb:
            msg = f"✅ 下载完成\n📄 {file_name}\n📦 {file_size_mb:.2f} MB\n⛔ 超过 {limit_mb}MB 不自动上传\n💾 服务器已保存"
            await self._send_text_msg(task_context, msg)
        else:
            await self._send_text_msg(task_context, f"✅ 下载完成 ({file_size_mb:.2f} MB)，正在上传...")
            await self._upload_via_napcat(task_context, local_path)
        
        self._remove_context(task_id)

    # --- 辅助工具 ---
    def _map_path(self, gopeed_path: str, config: GopeedConfig) -> str:
        path_str = gopeed_path.replace("\\", "/")
        if not config.remote_path_prefix or not config.local_path_prefix:
            return str(Path(path_str))
        remote_prefix = config.remote_path_prefix.replace("\\", "/")
        if path_str.startswith(remote_prefix):
            relative = path_str[len(remote_prefix):].lstrip('/')
            local_path = Path(config.local_path_prefix) / relative
            logger.info(f"[Gopeed] Path Map: {gopeed_path} -> {local_path}")
            return str(local_path)
        return str(Path(path_str))

    def _map_path_for_napcat(self, local_path: str, config: GopeedConfig) -> str:
        if not config.napcat_path_prefix:
            return os.path.abspath(local_path)
        
        local_abs = os.path.abspath(local_path).replace("\\", "/")
        local_prefix = config.local_path_prefix.replace("\\", "/")
        napcat_prefix = config.napcat_path_prefix.replace("\\", "/")
        
        if local_abs.lower().startswith(local_prefix.lower()):
            relative = local_abs[len(local_prefix):].lstrip("/")
            napcat_path = f"{napcat_prefix}/{relative}"
            logger.info(f"[Gopeed] NapCat Map: {local_abs} -> {napcat_path}")
            return napcat_path
        
        return local_abs

    def _sanitize_filename(self, url: str) -> str:
        try:
            path = url.split('?')[0]
            name = path.split('/')[-1]
            if not name: name = f"file_{int(time.time())}.dat"
            name = unquote(name)
            name = re.sub(r'[\\/:*?"<>|]', '_', name)
            name = re.sub(r'[\x00-\x1f]', '', name)
            if len(name) > 120:
                p = Path(name)
                name = f"{p.stem[:100]}{p.suffix}"
            return name
        except: return f"download_{int(time.time())}.dat"

    # --- 发送逻辑 ---
    async def _send_text_msg(self, context: dict, message: str):
        bot = self._get_bot()
        if not bot: return
        try:
            if context.get("type") == "group":
                await bot.api.call_action("send_group_msg", group_id=context.get("id"), message=message)
            else:
                await bot.api.call_action("send_private_msg", user_id=context.get("id"), message=message)
        except Exception as e:
            logger.error(f"[Gopeed] Send Error: {e}")

    async def _upload_via_napcat(self, context: dict, file_path: str):
        bot = self._get_bot()
        if not bot: return
        
        config = self._get_current_config()
        target_path = self._map_path_for_napcat(file_path, config)
        name = os.path.basename(file_path)
        
        logger.info(f"[Gopeed] Uploading: {target_path}")

        try:
            if context.get("type") == "group":
                await bot.api.call_action("upload_group_file", group_id=context.get("id"), file=target_path, name=name)
            else:
                await bot.api.call_action("upload_private_file", user_id=context.get("id"), file=target_path, name=name)
        except Exception as e:
            await self._send_text_msg(context, f"❌ 上传失败: {e}")

    # --- 任务创建 ---
    async def _add_task(self, url: str, user_id: str) -> tuple[bool, str, str]:
        config = self._get_current_config()
        if not config.api_token: return False, "缺少 api_token", ""

        url = html.unescape(url.strip())
        base_url = config.gopeed_host.rstrip("/")
        api_url = f"{base_url}/api/v1/tasks"
        
        raw_name = self._sanitize_filename(url)
        name_stem = Path(raw_name).stem
        name_suffix = Path(raw_name).suffix
        unique_name = f"{name_stem}_{int(time.time())}{name_suffix}"
        
        payload = {"req": {"url": url}, "opt": {"name": unique_name}}
        if config.download_path: payload["opt"]["path"] = config.download_path
        headers = {"Content-Type": "application/json", "X-Api-Token": config.api_token}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=payload, headers=headers, timeout=10) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        task_id = ""
                        try:
                            if text:
                                data = json.loads(text)
                                if isinstance(data, str): task_id = data
                                elif isinstance(data, dict): task_id = data.get("id") or data.get("data")
                        except: task_id = text.strip('"')

                        if task_id:
                            self.history.add_record(str(task_id), url, str(user_id), unique_name)
                            return True, str(task_id), unique_name
                        else:
                            return False, f"无法获取 TaskID: {text}", ""
                    else:
                        return False, f"HTTP {resp.status}", ""
        except Exception as e:
            return False, f"连接错误: {e}", ""

    # --- 指令 ---
    @filter.command("dl")
    async def dl_cmd(self, event: AstrMessageEvent, url: str):
        config = self._get_current_config()
        if config.webhook_server_port == 0:
            await event.send(MessageChain([Plain("❌ 插件配置错误：必须设置 Webhook 端口才能使用。")]))
            return

        user_id = event.get_sender_id()
        success, info, name = await self._add_task(url, user_id)
        if success:
            task_id = info
            self._register_context(task_id, event)
            await event.send(MessageChain([Plain(f"🚀 任务ID: {task_id}\n📄 {name}\n⏳ 已提交")]))
        else:
            await event.send(MessageChain([Plain(f"❌ 失败: {info}")]))

    @filter.regex(r"(https?://[^\s]+)")
    async def auto_dl(self, event: AstrMessageEvent):
        config = self._get_current_config()
        if not config.auto_download_mode: return
        if config.webhook_server_port == 0: return

        urls = re.findall(r"https?://[^\s]+", event.message_str)
        user_id = event.get_sender_id()
        for url in urls:
            if url.endswith(('.jpg', '.png', '.gif', '.json')): continue
            if "localhost" in url or "127.0.0.1" in url: continue
            url = url.replace('\\', '')
            
            success, info, name = await self._add_task(url, user_id)
            if success:
                task_id = info
                self._register_context(task_id, event)
                await event.send(MessageChain([Plain(f"🚀 自动捕获: {name}\nID: {task_id}")]))