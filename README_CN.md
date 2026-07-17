# Mr. Banana

<p align="center">
  <img src="https://raw.githubusercontent.com/cailurus/MrBanana/main/web/public/favicon.svg" alt="Mr. Banana Logo" width="120" height="120">
</p>

<p align="center">
  <strong>Jable.tv 视频下载器 & JAV 媒体库管理，带 Web UI</strong>
</p>

<p align="center">
  <a href="https://github.com/cailurus/MrBanana/releases"><img src="https://img.shields.io/github/v/release/cailurus/MrBanana?style=flat-square&color=blue" alt="GitHub Release"></a>
  <a href="https://github.com/cailurus/MrBanana/blob/main/LICENSE"><img src="https://img.shields.io/github/license/cailurus/MrBanana?style=flat-square" alt="License"></a>
  <a href="https://hub.docker.com/r/cailurus/mr-banana"><img src="https://img.shields.io/docker/pulls/cailurus/mr-banana?style=flat-square&logo=docker&logoColor=white" alt="Docker Pulls"></a>
  <a href="#windows-快速启动"><img src="https://img.shields.io/badge/Windows-PS%20脚本-0078D6?style=flat-square&logo=powershell&logoColor=white" alt="Windows"></a>
  <a href="https://github.com/cailurus/MrBanana/stargazers"><img src="https://img.shields.io/github/stars/cailurus/MrBanana?style=flat-square&color=yellow" alt="GitHub Stars"></a>
</p>

<p align="center">
  <a href="./README.md">English</a>
</p>

---

## 功能特性

- **⚡ 高速下载** — 从 Jable.tv 并发下载 HLS 视频，Cookie 注入自动绕过 Cloudflare（无需启动浏览器），FFmpeg 合并分段
- **📚 批量下载** — 提交 jable.tv 列表页 URL（收藏 / 稍后观看），一键排程下载全部影片
- **🏷️ 元数据刮削** — 扫描本地文件夹，从 JavDB、JavBus、DMM、JavTrailers、ThePornDB 获取元数据，生成 Kodi 兼容的 NFO 和封面图
- **🖥️ Web UI** — React 界面，支持下载队列、刮削、订阅管理和媒体库浏览
- **🔔 订阅追踪** — 监控 JavDB 磁力链接更新，支持 Telegram 通知
- **📡 油猴脚本** — Tampermonkey 扩展，在 JavDB 和 Jable 网站上一键下载/订阅
- **⏸️ 暂停续传** — 取消下载后保留已完成分段，续传时自动跳过，节省流量
- **🔐 Cloudflare 绕过** — 从已登录的 Chrome 浏览器自动提取 cookie，后续下载零浏览器开销

## Windows 快速启动

```powershell
.\run.ps1
```

1. 自动启动 Chrome（带 CDP 调试端口）用于 cookie 提取
2. 打开 jable.tv 登录页 — 登录后按任意键
3. 自动提取 cookie → 写入配置 → 启动服务器
4. 打开 http://127.0.0.1:8000

无需手动激活 `.venv`。

## Docker 部署（推荐）

```bash
docker run -d \
  --name mr-banana \
  -p 8000:8000 \
  -v /your/config:/config \
  -v /your/media:/data \
  -e ALLOWED_BROWSE_ROOTS="/data" \
  cailurus/mr-banana:latest
```

浏览器访问 http://localhost:8000

> **注意：** Docker 镜像首次使用 Patchright（Chromium）绕过 Cloudflare。在 Web UI → 下载设置中添加 jable.tv cookie 后，下载将使用快速 cookie 直连模式。

### Docker Compose

```yaml
services:
  mr-banana:
    image: cailurus/mr-banana:latest
    container_name: mr-banana
    ports:
      - "8000:8000"
    volumes:
      - /your/config:/config
      - /your/media:/data
    environment:
      - ALLOWED_BROWSE_ROOTS=/data
    restart: unless-stopped
```

### 卷挂载

| 容器路径 | 说明 | 宿主机路径示例 |
|----------|------|---------------|
| `/config` | 配置、数据库、日志（持久化） | `/volume/mrbanana/config` |
| `/data` | 媒体文件（视频、下载） | `/volume/data` |

`/config` 目录包含：`config.json`、`mr_banana_subscription.db`、`logs/`

## 架构

```
前端 (React / Vite)
    ↓  REST /api/* + WebSocket /ws
API 层 (FastAPI)
    ↓
管理器 (下载 / 刮削 / 订阅)
    ↓
核心库
    ├── 下载器 → Jable 提取器 → HLS（curl_cffi 或 Patchright）
    ├── 刮削器 → 爬虫 (JavDB, JavBus, DMM, ...) → NFO 写入
    └── 工具 (配置, 历史, 网络, 浏览器, 翻译)
```

## 本地开发

### 环境要求

- Python 3.10+
- Node.js 18+
- FFmpeg
- （可选）Chrome 用于 CDP cookie 提取

### 安装

```bash
git clone https://github.com/cailurus/MrBanana.git
cd MrBanana
python -m venv .venv && .venv\Scripts\activate  # Windows
pip install -r requirements.txt
cd web && npm install && cd ..
```

### 开发模式

```bash
make dev           # FastAPI :8000 + Vite :5173 热重载
# 或
.\run.ps1          # 单窗口：构建前端 + 启动 FastAPI
```

### 生产构建

```bash
make fe            # 构建前端 → ./static
make serve         # FastAPI 提供 ./static 在 :8000
```

## 命令行用法

```bash
python -m mr_banana.cli --url <视频URL> --output_dir <输出目录>
```

| 参数 | 说明 |
|------|------|
| `--url` | Jable.tv 视频地址（必填） |
| `--output_dir` | 输出目录 |
| `--format` | 文件名格式 — 支持 `{id}` 和 `{title}` |
| `-v` | 详细日志 |

## 新增 API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/download/batch` | 从 jable.tv 列表页批量排程下载 |
| `GET` | `/api/download/batch/preview` | 预览 jable.tv 列表页视频 |
| `GET` | `/api/jable/lists` | 获取收藏和稍后观看列表（CDP 分页） |
| `POST` | `/api/jable/login` | 通过 CDP cookie 提取或手动浏览器登录 |

## 浏览器油猴脚本

1. 安装 [Tampermonkey](https://www.tampermonkey.net/)
2. 点击安装：[mrbanana-helper.user.js](https://raw.githubusercontent.com/cailurus/MrBanana/main/userscripts/mrbanana-helper.user.js)
3. 在 Tampermonkey 设置中配置 Mr. Banana 服务器地址

**支持的网站：**
- **JavDB** — 详情页添加「订阅到 Mr. Banana」按钮
- **Jable** — 视频页添加「下载到 Mr. Banana」按钮

## Cookie 管理

Mr. Banana 可以从已登录的 Chrome 浏览器中提取 Cloudflare 绕过 cookie：

```bash
# 方法一：通过 CDP 自动提取（需要 Chrome 运行在端口 9222）
python scripts/mcp_cdp_cookie_server.py

# 方法二：浏览器控制台
# 打开 jable.tv → F12 → Console → 粘贴 scripts/extract_jable_cookie.js → Enter
```

将 cookie 字符串粘贴到 **Web UI → 下载设置 → Jable Cookie**。后续下载将使用快速 cookie 直连模式（无需启动浏览器）。

## 环境变量

| 名称 | 说明 | 默认值 |
|------|------|--------|
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `MR_BANANA_LOG_LEVEL` | 覆盖日志级别 | `INFO` |
| `MR_BANANA_CONFIG_DIR` | 配置文件目录 | `/config`（Docker） |
| `ALLOWED_BROWSE_ROOTS` | Web UI 可浏览的目录 | `/data` |
| `CORS_ORIGINS` | CORS 允许的源 | `*` |

## 许可证

[MIT License](LICENSE)