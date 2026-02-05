# PaperNews 快速启动指南

## 5 分钟快速启动

### 1. 环境准备 (1分钟)

```bash
# 确保已安装 uv
uv --version

# 进入项目目录
cd PaperNews

# 安装依赖
uv sync
```

### 2. 配置环境变量 (2分钟)

```bash
# 创建 .env 文件
cat > .env << 'EOF'
# Telegram Bot Token (必需)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# AI API Key (至少配置一个)
OPENAI_API_KEY=sk-your_key_here
# 或
ANTHROPIC_API_KEY=sk-your_key_here

# 其他配置（可选）
TIMEZONE=Asia/Shanghai
DAILY_BRIEFING_HOUR=9
DAILY_BRIEFING_MINUTE=0
EOF
```

**获取 Bot Token**:
1. Telegram 搜索 `@BotFather`
2. 发送 `/newbot`
3. 按提示创建机器人
4. 复制 Token 到 `.env`

### 3. 初始化数据库 (1分钟)

```bash
uv run python -c "from src.models import init_database; init_database()"
```

### 4. 启动系统 (1分钟)

#### 方式 A: 仅启动机器人（测试用）

```bash
uv run python main.py bot
```

在 Telegram 中找到你的机器人，发送 `/start`

#### 方式 B: 启动完整系统（生产用）

```bash
uv run python main.py scheduler
```

系统会自动：
- 启动 Telegram 机器人
- 定时爬取论文
- 生成简报
- 推送给用户

---

## 常用命令

### 用户命令 (Telegram)

```
/start      - 开始使用
/fields     - 选择研究领域
/settings   - 查看设置
/limit 10   - 设置每日10篇
/history 7  - 设置历史7天
/next       - 获取下一条简报
/history    - 查看历史简报
/stats      - 查看统计
/help       - 帮助
```

### 管理命令 (终端)

```bash
# 手动爬取论文
uv run python main.py fetch

# 手动生成简报
uv run python main.py generate

# 手动发送简报
uv run python main.py send

# 执行全部任务
uv run python main.py run-all
```

---

## 系统工作流程

```
每天 06:00  - 爬取论文
每天 07:00  - 生成简报
每天 09:00  - 推送给用户 (可配置)
```

用户也可以随时发送 `/next` 主动获取简报。

---

## 研究领域

系统预置6个研究领域：

1. **机器学习** - cs.LG, cs.AI, stat.ML
2. **自然语言处理** - cs.CL
3. **计算机视觉** - cs.CV
4. **机器人学** - cs.RO
5. **强化学习** - cs.LG, cs.AI, cs.MA
6. **AI安全与对齐** - cs.AI, cs.LG, cs.CY

用户首次使用 `/start` 时需选择感兴趣的领域。

---

## 故障排查

### 机器人无响应

```bash
# 检查 Token 是否正确
grep TELEGRAM_BOT_TOKEN .env

# 检查日志
uv run python main.py bot
# 查看终端输出
```

### 没有收到简报

1. 检查是否完成领域选择：`/fields`
2. 检查是否启用推送：`/settings`
3. 手动触发：`/next`

### 数据库错误

```bash
# 重置数据库
rm data/papernews.db
uv run python -c "from src.models import init_database; init_database()"
```

---

## 配置文件示例

完整 `.env` 配置：

```bash
# 必需
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11

# AI 服务 (至少一个)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx

# 可选
DATABASE_URL=sqlite:///data/papernews.db
TIMEZONE=Asia/Shanghai
DAILY_BRIEFING_HOUR=9
DAILY_BRIEFING_MINUTE=0
ARXIV_MAX_RESULTS=100
MAX_PAPERS_PER_DAY=20
```

---

## 下一步

- 详细文档：[PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)
- 查看日志：`tail -f logs/papernews.log`
- 数据库管理：`sqlite3 data/papernews.db`

---

**有问题？** 检查 PROJECT_DOCUMENTATION.md 的故障排查章节。
