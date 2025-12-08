# AstrBot Plugin Click2Download 🚀

<div align="center">

**将您的聊天机器人打造为全能下载中心**

远程控制 Gopeed • 实时 Webhook 推送 • 自动回传 QQ • 历史记录 • 自动清理

</div>

---

## 🇨🇳 简体中文 (Chinese)

### 📖 简介 (Introduction)

**astrbot_plugin_click2download** 是一个专为 AstrBot 设计的高级插件，深度集成了 **Gopeed** 下载器。

它不仅仅是一个简单的下载指令封装，而是一个完整的下载生命周期管理系统。通过 Webhook 技术，它实现了毫秒级的下载完成通知，并能根据文件大小智能决策是直接上传文件还是仅发送路径。

### ✨ 核心特性 (Features)

| 特性 | 说明 | 优势 |
| :--- | :--- | :--- |
| **⚡ Webhook 驱动** | 利用 Webhook 实现下载完成的实时响应 | 拒绝低效的轮询 (Polling)，响应速度达到毫秒级 |
| **🔄 上下文持久化** | 记录任务发起的群组/用户，重启不丢失 | 即使 Bot 在下载中途重启，下载完成后依然能准确推送给原用户 |
| **📂 智能回传** | < 500MB 直接上传；> 500MB 发送路径 | 兼顾便捷性与服务器稳定性，防止大文件导致超时或网络拥堵 |
| **🐳 Docker 友好** | 内置强大的路径映射 (Path Mapping) | 完美解决 Docker 容器内外路径不一致的痛点 |
| **🧹 自动清理** | 自动删除超过指定时间（默认 24h）的文件 | 维护服务器磁盘整洁，无需手动管理 |
| **📊 历史记录** | 完整的 JSON 数据库记录 | 包含文件名、大小、耗时、用户ID等详细信息 |

### 📂 目录结构 (Structure)

```text
astrbot_plugin_click2download/
├── main.py             # 核心逻辑 (Webhook服务, API调用)
├── history.py          # 历史记录数据库管理
├── cleaner.py          # 过期文件自动清理线程
├── config.json         # 用户配置文件 (自动生成)
├── _conf_schema.json   # 配置校验文件
├── __init__.py         # 包标识
└── README.md           # 说明文档
```

### 🛠️ 快速开始 (Getting Started)

#### 1. 安装插件
将本仓库解压至 AstrBot 的插件目录：
```bash
./data/plugins/astrbot_plugin_click2download/
```
或在插件商城中搜索“链接下载”

#### 2. 配置 AstrBot
启动一次 AstrBot 以生成配置文件，然后在 Web 管理面板或 `config.json` 中修改：

| 配置项 (Key) | 必填 | 默认值 | 说明 |
| :--- | :---: | :---: | :--- |
| `gopeed_host` | ✅ | `http://127.0.0.1:9999` | Gopeed 服务端 API 地址 |
| `api_token` | ✅ | - | **重要**：Gopeed 的 API Token (在 Gopeed 设置中获取) |
| `webhook_server_port` | ✅ | `0` | **必须修改** (如 18080)，Bot 监听此端口接收 Gopeed 通知 |
| `upload_size_limit_mb` | ❌ | `500` | 超过此大小的文件不自动上传，仅通知路径 |
| `auto_delete_hours` | ❌ | `24` | 下载完成后多少小时自动删除文件 (0 为永久保留) |
| `remote_path_prefix` | ❌ | - | (Docker用) **Gopeed 容器内**看到的下载路径前缀 |
| `local_path_prefix` | ❌ | - | (Docker用) **Bot 容器/宿主机**对应的真实路径前缀 |

#### 3. 配置 Gopeed Webhook (关键步骤)
为了让 Bot 知道下载何时完成，您必须在 Gopeed 中配置回调：

1.  打开 Gopeed Web 界面。
2.  进入 **设置 (Settings)** -> **高级设置 (Advanced)**。
3.  找到 **Webhook** 选项。
4.  填入 Bot 的监听地址：
    ```text
    http://<Bot所在IP>:<webhook_server_port>/webhook
    
    # 示例
    [http://192.168.1.5:18080/webhook]
    ```
5.  点击“测试连接”，如果 Bot 后台日志提示收到请求，则配置成功。

---

### 🐳 Docker 部署指南 (Docker Setup)

在 Docker 环境下，**路径映射**和**网络互通**是成功的关键。

#### 1. 端口映射
Bot 需要暴露 Webhook 端口供 Gopeed 访问。

```bash
docker run -d \
  --name astrbot \
  -p 6125:6125 \
  -p 18080:18080 \  # <--- 必须映射 Webhook 端口
  -v /mnt/data:/data \
  astrbot/astrbot
```

#### 2. 共享下载目录 (路径映射)
Bot 必须能读取到 Gopeed 下载的文件。
假设宿主机真实下载目录为：`/home/user/downloads`

| 角色 | 挂载参数 (`-v`) | 容器内路径 | 说明 |
| :--- | :--- | :--- | :--- |
| **Gopeed** | `-v /home/user/downloads:/app/downloads` | `/app/downloads` | 下载器将文件写入此路径 |
| **AstrBot** | `-v /home/user/downloads:/bot_downloads` | `/bot_downloads` | 机器人从此路径读取文件 |

**此时插件配置 (`config.json`) 应填写：**

```json
{
  "remote_path_prefix": "/app/downloads",
  "local_path_prefix": "/bot_downloads"
}
```
*插件会自动将路径前缀进行替换，确保 Bot 能找到文件。*

---

### 📊 数据记录 (Data Persistence)

为了防止插件更新导致数据丢失，所有的历史记录数据将存储在 AstrBot 的公共数据目录下：

`./data/plugin_data/astrbot_plugin_click2download/`

* **history.json**: 完整的下载历史记录（包含时间戳、大小、用户ID等）。
* **context_map.json**: 任务上下文映射（用于断电重启后的回复）。

---

## 🇺🇸 English

A comprehensive AstrBot plugin that turns your chatbot into a remote controller for Gopeed downloader. Features Webhook notifications, Persistence, Auto-upload, and Auto-cleaning.

### ✨ Key Features

| Feature | Description |
| :--- | :--- |
| **Webhook Driven** | Instant notifications via Gopeed Webhook, no polling required. |
| **Persistence** | Remembers the task context (User/Group) even after a bot restart. |
| **Smart Upload** | Automatically uploads files smaller than the limit; notifies path for larger files. |
| **Auto Cleaner** | Automatically deletes local files after a configurable retention period (default 24h). |
| **Docker Ready** | Supports path mapping for complex Docker/Remote setups. |

### 🛠️ Setup

#### 1. Configure Plugin
Edit `config.json` or use the AstrBot WebUI:

| Key | Required | Description |
| :--- | :---: | :--- |
| `api_token` | Yes | Get this from Gopeed settings. |
| `webhook_server_port` | Yes | Local port for the bot to listen on (e.g., 18080). |
| `auto_delete_hours` | No | Time in hours to keep files (0 to disable). |

#### 2. Configure Gopeed
1.  Go to Gopeed **Settings** -> **Advanced**.
2.  Set Webhook URL to: `http://<Bot_IP>:<webhook_server_port>/webhook`.
3.  Click **test** to verify.

#### 3. Docker Path Mapping
If running in Docker, map the paths so the bot can access files downloaded by Gopeed.

| Config Key | Description |
| :--- | :--- |
| `remote_path_prefix` | The path Gopeed sees inside its container. |
| `local_path_prefix` | The path AstrBot sees (must map to the same physical location). |

---

### 📄 License

MIT License
