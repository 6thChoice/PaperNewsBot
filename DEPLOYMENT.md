# PaperNews 正式部署指南

## 📋 前置要求

1. Python 3.9+
2. uv 包管理器
3. Telegram 账号
4. (可选) OpenAI API Key 或 Anthropic API Key

---

## 🔧 第一步：配置环境变量

### 1. 复制环境变量模板

```bash
cp .env.example .env
```

### 2. 编辑 .env 文件

```bash
# 使用你喜欢的编辑器
vim .env
# 或
nano .env
```

### 3. 必须配置的项

#### Telegram Bot 配置（必需）

```env
# Telegram Bot Token（从 @BotFather 获取）
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Telegram Chat ID（你的用户 ID 或群组 ID）
TELEGRAM_CHAT_ID=your_chat_id_here
```

#### AI API 配置（可选但推荐）

```env
# OpenAI API Key（用于生成高质量简报）
OPENAI_API_KEY=sk-your_openai_api_key

# 或 Anthropic API Key（备选）
ANTHROPIC_API_KEY=sk-ant-your_anthropic_key
```

#### AI API Base URL 配置（可选）

用于适配不同厂商的大模型服务（如 Azure OpenAI、国内代理等）：

```env
# OpenAI 格式 API 的自定义 Base URL
# 默认: https://api.openai.com/v1
# 示例（Azure OpenAI）:
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment
# 示例（第三方代理）:
OPENAI_BASE_URL=https://api.example.com/v1

# Anthropic 格式 API 的自定义 Base URL
# 默认: https://api.anthropic.com
ANTHROPIC_BASE_URL=https://your-custom-endpoint.com
```

> 💡 **提示**: 如果不配置 AI API，系统会使用备用摘要模式（只显示论文摘要）

#### 应用配置（可选，使用默认值即可）

```env
# 调试模式
debug=false

# 日志级别
LOG_LEVEL=INFO

# 时区
TIMEZONE=Asia/Shanghai

# 数据库路径
DATABASE_URL=sqlite:///data/papernews.db

# arXiv 论文分类（逗号分隔）
ARXIV_CATEGORIES=cs.AI,cs.CL,cs.CV,cs.LG,cs.RO,cs.SY

# 每日最大论文数
MAX_PAPERS_PER_DAY=10

# 每日简报发送时间
DAILY_BRIEFING_HOUR=9
DAILY_BRIEFING_MINUTE=0

# 用户兴趣关键词（逗号分隔）
USER_INTERESTS=machine learning,natural language processing,computer vision,deep learning,reinforcement learning
```

---

## 🤖 第二步：创建 Telegram Bot

### 1. 获取 Bot Token

1. 打开 Telegram，搜索 `@BotFather`
2. 发送 `/start` 开始对话
3. 发送 `/newbot` 创建新机器人
4. 按提示输入机器人名称和用户名
5. 复制获得的 **Bot Token**（格式：`123456789:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 2. 获取 Chat ID

#### 方法 A：通过机器人获取（推荐）

1. 向你的机器人发送任意消息
2. 浏览器访问：
   ```
   https://api.telegram.org/bot<你的BotToken>/getUpdates
   ```
3. 在返回的 JSON 中查找 `chat.id` 字段

#### 方法 B：通过 @userinfobot

1. 在 Telegram 搜索 `@userinfobot`
2. 发送任意消息，会返回你的用户 ID

#### 方法 C：如果是群组

1. 将机器人添加到群组
2. 发送一条消息
3. 访问 `getUpdates` API（同方法 A）
4. 查找 `chat.id`（群组 ID 通常是负数，如 `-123456789`）

---

## 🚀 第三步：运行服务

### 方式 1：手动运行单次任务

```bash
# 爬取论文
uv run python main.py fetch

# 生成简报
uv run python main.py generate

# 发送简报
uv run python main.py send

# 运行完整流程（爬取+生成+发送）
uv run python main.py all
```

### 方式 2：启动定时任务调度器（推荐）

```bash
# 启动调度器（后台持续运行）
uv run python main.py scheduler
```

调度器会自动执行：
- 每天 06:00 爬取论文
- 每天 07:00 生成简报
- 每天 09:00 发送简报

### 方式 3：仅启动 Telegram 机器人

```bash
# 只启动机器人（可交互，但不会自动爬取和发送）
uv run python main.py bot
```

---

## 🔄 第四步：与机器人交互

启动机器人后，在 Telegram 中可以使用以下命令：

| 命令 | 功能 |
|-----|------|
| `/start` | 开始使用，显示欢迎信息 |
| `/help` | 显示帮助信息 |
| `/list` | 查看所有简报 |
| `/today` | 查看今日待发送简报 |
| `/search <关键词>` | 搜索论文 |
| `/read <ID>` | 标记论文为已读 |
| `/interested <ID>` | 标记感兴趣的论文 |
| `/stats` | 查看统计信息 |

---

## 🖥️ 第五步：后台运行（生产环境）

### 使用 nohup

```bash
# 后台运行调度器
nohup uv run python main.py scheduler > logs/scheduler.log 2>&1 &

# 查看进程
ps aux | grep main.py

# 停止进程
kill <进程ID>
```

### 使用 systemd（Linux）

创建服务文件 `/etc/systemd/system/papernews.service`：

```ini
[Unit]
Description=PaperNews Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/PaperNews
ExecStart=/usr/local/bin/uv run python main.py scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用和启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable papernews
sudo systemctl start papernews

# 查看状态
sudo systemctl status papernews

# 查看日志
sudo journalctl -u papernews -f
```

### 使用 Docker（推荐）

创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制项目文件
COPY pyproject.toml .
COPY src/ ./src/
COPY main.py .

# 安装依赖
RUN uv pip install -e "."

# 创建数据目录
RUN mkdir -p data logs

# 运行调度器
CMD ["uv", "run", "python", "main.py", "scheduler"]
```

构建和运行：

```bash
# 构建镜像
docker build -t papernews .

# 运行容器
docker run -d \
  --name papernews \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  papernews
```

### 使用 Docker Compose

创建 `docker-compose.yml`：

```yaml
version: '3.8'

services:
  papernews:
    build: .
    container_name: papernews
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
```

运行：

```bash
docker-compose up -d
```

---

## 🔍 第六步：监控和日志

### 查看日志

```bash
# 实时查看日志
tail -f logs/papernews.log

# 查看最近 100 行
tail -n 100 logs/papernews.log
```

### 检查数据库

```bash
# 使用 SQLite CLI
sqlite3 data/papernews.db

# 常用查询
SELECT COUNT(*) FROM papers;
SELECT COUNT(*) FROM briefings;
SELECT COUNT(*) FROM briefings WHERE is_sent = 0;
```

---

## ⚠️ 常见问题

### 1. Telegram 收不到消息

- 检查 `TELEGRAM_BOT_TOKEN` 是否正确
- 检查 `TELEGRAM_CHAT_ID` 是否正确
- 确保已向机器人发送过 `/start`
- 查看日志中的错误信息

### 2. AI 简报生成失败

- 检查 API Key 是否有效
- 检查 API Key 是否有余额
- 不配置 API Key 时会使用备用模式

### 3. 无法爬取论文

- 检查网络连接
- arXiv 和 OpenReview 在国内可能需要代理
- 查看日志中的网络错误

### 4. 数据库锁定

- SQLite 不支持多进程并发写入
- 确保只有一个调度器实例在运行
- 或使用 PostgreSQL 替代 SQLite

---

## 📝 更新和维护

### 更新代码

```bash
git pull
uv pip install -e ".[dev]"
```

### 备份数据

```bash
# 备份数据库
cp data/papernews.db data/papernews.db.backup

# 备份日志
tar -czvf logs-backup.tar.gz logs/
```

### 清理旧数据

```bash
# 进入数据库
sqlite3 data/papernews.db

-- 删除 30 天前的论文
DELETE FROM papers WHERE created_at < datetime('now', '-30 days');

-- 删除已发送的简报
DELETE FROM briefings WHERE is_sent = 1 AND created_at < datetime('now', '-7 days');
```

---

## 🎉 完成！

配置完成后，你的 PaperNews 服务将会：

1. ✅ 每天自动爬取最新论文
2. ✅ 自动生成论文简报
3. ✅ 每天定时推送到 Telegram
4. ✅ 支持交互式命令查询

享受你的智能论文助手吧！📚🤖
