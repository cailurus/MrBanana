# Mr. Banana

<p align="center">
  <img src="https://raw.githubusercontent.com/cailurus/MrBanana/main/web/public/favicon.svg" alt="Mr. Banana Logo" width="120" height="120">
</p>

<p align="center">
  <strong>从 Jable.tv 下载视频 & 本地视频库刮削工具，带 Web UI</strong>
</p>

<p align="center">
  <a href="https://github.com/cailurus/MrBanana/releases"><img src="https://img.shields.io/github/v/release/cailurus/MrBanana?style=flat-square&color=blue" alt="GitHub Release"></a>
  <a href="https://github.com/cailurus/MrBanana/blob/main/LICENSE"><img src="https://img.shields.io/github/license/cailurus/MrBanana?style=flat-square" alt="License"></a>
  <a href="https://hub.docker.com/r/cailurus/mr-banana"><img src="https://img.shields.io/docker/pulls/cailurus/mr-banana?style=flat-square&logo=docker&logoColor=white" alt="Docker Pulls"></a>
  <a href="https://hub.docker.com/r/cailurus/mr-banana"><img src="https://img.shields.io/docker/image-size/cailurus/mr-banana/latest?style=flat-square&logo=docker&logoColor=white&label=image%20size" alt="Docker Image Size"></a>
  <a href="https://github.com/cailurus/MrBanana/stargazers"><img src="https://img.shields.io/github/stars/cailurus/MrBanana?style=flat-square&color=yellow" alt="GitHub Stars"></a>
</p>

<p align="center">
  <a href="./README.md">English</a>
</p>

---

## 功能特性

- **视频下载** — 从 Jable.tv 并发下载 HLS 视频，自动绕过 Cloudflare，通过 FFmpeg 合并分段
- **元数据刮削** — 扫描本地文件夹，从多个数据源（JavDB、JavBus、DMM、JavTrailers、ThePornDB）获取元数据，生成 Kodi 兼容的 NFO 文件和封面图
- **Web UI** — 基于 React 的界面，支持批量下载、刮削、订阅管理和媒体库浏览
- **订阅追踪** — 监控 JavDB 上的磁力链接更新，支持 Telegram 通知
- **CLI** — 命令行下载工具
- **浏览器油猴脚本** — 在 JavDB 和 Jable 网站上一键下载/订阅

## 架构

```
前端 (React / Vite)
    ↓  REST /api/* + WebSocket /ws
API 层 (FastAPI)
    ↓
管理器 (下载 / 刮削 / 订阅)
    ↓
核心库
    ├── 下载器 → Jable 提取器 → HLS 下载
    ├── 刮削器 → 爬虫 (JavDB, JavBus, DMM, ...) → NFO 写入
    └── 工具 (配置, 历史, 网络, 浏览器, 翻译)
```

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

浏览器访问 http://localhost:8000 即可使用。

### 卷挂载

| 容器路径 | 说明 | 宿主机路径示例 |
|----------|------|---------------|
| `/config` | 配置文件、数据库、日志（更新容器后保留） | `/volume/mrbanana/config` |
| `/data` | 媒体文件（视频、下载） | `/volume/data` |

`/config` 目录包含：
- `config.json` — 应用设置
- `mr_banana_subscription.db` — 订阅数据库
- `logs/` — 应用日志

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

## 本地开发

### 环境要求

- Python 3.10+
- Node.js 18+
- FFmpeg
- patchright + Chromium（首次运行 `patchright install chromium`）

### 安装

```bash
git clone https://github.com/cailurus/MrBanana.git
cd MrBanana
python3 -m venv .venv && source .venv/bin/activate
make py-install    # 安装 Python 依赖
make web-install   # 安装 Node 依赖
```

### 开发模式

```bash
make dev           # FastAPI :8000 + Vite :5173 热重载
make test          # 运行测试
make test-quick    # 运行测试（简洁输出）
```

### 生产构建

```bash
make fe            # 构建前端 → ./static
make serve         # FastAPI 在 :8000 提供服务
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

## 浏览器油猴脚本

1. 安装 [Tampermonkey](https://www.tampermonkey.net/)
2. 点击安装：[mrbanana-helper.user.js](https://raw.githubusercontent.com/cailurus/MrBanana/main/userscripts/mrbanana-helper.user.js)
3. 在 Tampermonkey 设置中配置 Mr. Banana 服务器地址

**支持的网站：**
- **JavDB** — 详情页添加「订阅到 Mr. Banana」按钮
- **Jable** — 视频页添加「下载到 Mr. Banana」按钮

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
