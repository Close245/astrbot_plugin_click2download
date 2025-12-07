# **astrbot_plugin_click2download**

**\[中文\]**

一个功能强大的 AstrBot 插件，将您的聊天机器人转变为 Gopeed 下载器的远程控制中心。  
支持 Webhook 实时推送、任务持久化、断点续传、自动回传 以及 过期文件自动清理。  
\</div\>

## **✨ 核心特性 (Features)**

* ⚡ **Webhook 驱动**：利用 Gopeed 的 Webhook 功能实现零延迟的任务完成通知，告别低效轮询。  
* 🔄 **持久化记忆**：Bot 重启不丢失任务上下文。无论何时下载完成，Bot 都能准确找到当初发送指令的用户并推送文件。  
* 📂 **智能回传**：  
  * 小文件（\< 500MB，可配置）：自动上传至 QQ/Telegram。  
  * 大文件：仅发送保存路径，防止上传超时或刷屏。  
* 🧹 **自动清理**：内置清理线程，自动删除下载超过 24 小时（可配置）的本地文件，节省服务器空间。  
* 🐳 **Docker 友好**：完美的路径映射支持，轻松解决 Docker 容器内外路径不一致的问题。  
* 🕵️ **自动嗅探**：支持识别聊天记录中的链接并自动建立下载任务（可选）。

## **🛠️ 安装与配置 (Installation)**

### **1\. 安装插件**

将本仓库克隆或解压至 AstrBot 的 data/plugins/astrbot\_plugin\_gopeed/ 目录下。

### **2\. 依赖安装**

插件依赖 aiohttp 和 pydantic，AstrBot 环境通常已内置。如有缺失请运行：

pip install aiohttp pydantic

### **3\. 配置文件 (config.json)**

首次运行插件后，会自动在 data/plugins/astrbot\_plugin\_gopeed/ 下生成 config.json。或者您可以在 AstrBot 的 Web 管理面板中进行配置。

| 配置项 | 必填 | 默认值 | 说明 |
| :---- | :---- | :---- | :---- |
| gopeed\_host | ✅ | http://127.0.0.1:9999 | Gopeed 服务端地址 |
| api\_token | ✅ | \- | Gopeed 的 API Token (在 Gopeed 设置中获取) |
| webhook\_server\_port | ✅ | 0 | **必须修改为非 0 端口** (如 18080)，Bot 将监听此端口接收通知 |
| upload\_size\_limit\_mb | ❌ | 500 | 自动上传的最大文件大小 (MB) |
| auto\_delete\_hours | ❌ | 24 | 下载完成后多少小时自动删除文件 (0 为不删除) |
| download\_path | ❌ | \- | 指定 Gopeed 的下载目录 |
| remote\_path\_prefix | ❌ | \- | (Docker必填) Gopeed 容器内看到的路径 |
| local\_path\_prefix | ❌ | \- | (Docker必填) Bot 容器/宿主机看到的路径 |

### **4\. Gopeed 端设置 (重要)**

为了让 Bot 接收通知，您**必须**在 Gopeed 中配置 Webhook：

1. 打开 Gopeed Web 界面。  
2. 进入 **设置 (Settings)** \-\> **高级设置 (Advanced)**。  
3. 在 **Webhook** 一栏填写 Bot 的监听地址：  
   http://\<Bot所在IP\>:\<webhook\_server\_port\>/webhook

   *例如: http://192.168.1.5:18080/webhook*  
4. 点击测试，如果 Bot 后台日志提示收到请求，则配置成功。

## **🐳 Docker / 跨容器部署指南**

如果您的 Bot 和 Gopeed 运行在 Docker 中，请务必阅读本节。

### **1\. 端口映射**

Bot 需要监听 Webhook 端口（如 18080），请确保在启动 AstrBot 容器时映射了该端口：

docker run \-p 6125:6125 \-p 18080:18080 ...

### **2\. 路径映射 (Path Mapping)**

Bot 需要读取 Gopeed 下载的文件进行上传。如果它们在不同的环境，路径会不一致。

**假设场景：**

* **宿主机下载目录**：/mnt/data/downloads  
* **Gopeed 容器挂载**：-v /mnt/data/downloads:/app/downloads  
* **AstrBot 容器挂载**：-v /mnt/data/downloads:/bot\_data/downloads

**此时文件路径差异：**

* Gopeed 告诉 Bot 文件在：/app/downloads/video.mp4  
* Bot 实际能访问的路径是：/bot\_data/downloads/video.mp4

**插件配置应为：**

{  
  "remote\_path\_prefix": "/app/downloads",  
  "local\_path\_prefix": "/bot\_data/downloads"  
}

插件会自动将路径前缀进行替换，确保 Bot 能找到文件。

## **📊 数据记录 (Data Persistence)**

为了防止插件更新导致数据丢失，所有的历史记录数据将存储在 AstrBot 的公共数据目录下：  
./data/plugin\_data/astrbot\_plugin\_click2download/

* history.json: 完整的下载历史记录（包含时间戳、大小、用户ID等）。  
* context\_map.json: 任务上下文映射（用于断电重启后的回复）。

# **English**

A comprehensive AstrBot plugin that turns your chatbot into a remote controller for Gopeed downloader. Features **Webhook notifications**, **Persistence**, **Auto-upload**, and **Auto-cleaning**.

## **✨ Key Features**

* **Webhook Driven**: Instant notifications via Gopeed Webhook, no polling required.  
* **Persistence**: Remembers the task context (User/Group) even after a bot restart.  
* **Smart Upload**: Automatically uploads files smaller than the limit; notifies path for larger files.  
* **Auto Cleaner**: Automatically deletes local files after a configurable retention period (default 24h).  
* **Docker Ready**: Supports path mapping for complex Docker/Remote setups.

## **🛠️ Setup**

### **1\. Configure Plugin**

Edit config.json or use the AstrBot WebUI:

* api\_token: **Required**. Get this from Gopeed settings.  
* webhook\_server\_port: **Required**. Local port for the bot to listen on (e.g., 18080).  
* auto\_delete\_hours: Time in hours to keep files (0 to disable).

### **2\. Configure Gopeed**

1. Go to Gopeed **Settings** \-\> **Advanced**.  
2. Set **Webhook** URL to: http://\<Bot\_IP\>:\<webhook\_server\_port\>/webhook.  
3. Click test to verify.

### **3\. Docker Path Mapping**

If running in Docker, map the paths so the bot can access files downloaded by Gopeed.

* remote\_path\_prefix: The path Gopeed sees inside its container.  
* local\_path\_prefix: The path AstrBot sees (must map to the same physical location).

## **📄 License**

MIT License
