# PaperNews - 学术论文追踪与简报系统

## 项目功能

1. **自动爬取论文**：追踪最新论文，挖掘以往论文
2. **AI 智能识别**：对符合用户兴趣的论文生成中文简报
3. **个性化推送**：根据用户订阅领域定时推送简报
4. **用户管理**：支持多用户、差异化配置
5. **历史文章支持**：可配置向前爬取历史文章

## 实现方案

### 论文来源
1. 从 arXiv 上爬取论文
2. 从 OpenReview 上爬取论文

### 论文识别
1. 纯代码提取论文元数据，包括标题、作者、摘要、关键词、发表日期、发表会议等
2. 对于符合用户需求的论文，由 AI 进行阅读并编写简报，储存在数据库中
3. 每日定时从数据库中提取简报，通过 Telegram 机器人发送给用户
4. 用户可以标注对论文的阅读情况，是否已读，是否感兴趣等
5. 用户可以在 Telegram 机器人中查看所有简报

## 文档导航

| 文档 | 说明 |
|------|------|
| [QUICK_START.md](QUICK_START.md) | **快速启动指南** - 5分钟快速上手 |
| [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md) | **完整项目文档** - 全流程说明、配置参数、部署指南 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | **架构设计文档** - 系统架构、数据模型、设计决策 |
| [OPERATIONS.md](OPERATIONS.md) | **运维手册** - 日常运维、故障处理、备份恢复 |

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 TELEGRAM_BOT_TOKEN 和 AI API Key

# 3. 初始化数据库
uv run python -c "from src.models import init_database; init_database()"

# 4. 启动系统
uv run python main.py scheduler
```

详细步骤请参考 [QUICK_START.md](QUICK_START.md)

## 系统架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   用户层     │────▶│ TelegramBot │────▶│   服务层     │
│ (Telegram)  │     │  (机器人)    │     │ (Services)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                       ┌────────────────────────┘
                       │
                       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  外部服务    │◀───▶│   数据层     │◀───▶│   爬虫层     │
│(arXiv/API)  │     │ (Database)  │     │ (Crawlers)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

详细架构请参考 [ARCHITECTURE.md](ARCHITECTURE.md)

## 核心功能

### 用户管理
- ✅ 用户注册与领域订阅
- ✅ 个性化推送设置（每日数量、历史天数）
- ✅ 多用户差异化配置

### 论文爬取
- ✅ arXiv 论文爬取
- ✅ OpenReview 论文爬取
- ✅ 历史文章支持（可配置天数）
- ✅ 自动去重

### 简报生成
- ✅ AI 智能生成简报
- ✅ 支持 OpenAI / Anthropic
- ✅ Fallback 模板机制
- ✅ 中文简报输出

### Telegram 机器人
- ✅ 交互式领域选择
- ✅ 实时简报推送
- ✅ 历史简报查询
- ✅ 阅读状态追踪

## 技术栈

- **Python 3.9+** - 开发语言
- **SQLAlchemy** - ORM 框架
- **SQLite** - 数据库（支持 PostgreSQL/MySQL）
- **python-telegram-bot** - Telegram Bot 框架
- **APScheduler** - 任务调度
- **OpenAI/Anthropic API** - AI 简报生成
- **uv** - 依赖管理

## 项目结构

```
PaperNews/
├── src/
│   ├── models/          # 数据模型
│   ├── crawlers/        # 爬虫模块
│   ├── services/        # 业务服务
│   ├── bot/             # Telegram 机器人
│   ├── config.py        # 配置管理
│   ├── scheduler.py     # 任务调度
│   └── main.py          # 程序入口
├── data/                # 数据目录
├── logs/                # 日志目录
├── .env                 # 环境变量
└── pyproject.toml       # 项目配置
```

## 部署方式

### 开发环境
```bash
uv run python main.py bot        # 仅启动机器人
uv run python main.py scheduler  # 启动完整系统
```

### 生产环境
推荐使用 systemd 或 Docker 部署，详见 [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)

## 常用命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用机器人 |
| `/fields` | 选择研究领域 |
| `/settings` | 查看当前设置 |
| `/limit 10` | 设置每日推送10篇 |
| `/history 7` | 设置历史爬取7天 |
| `/next` | 获取下一条简报 |
| `/history` | 查看历史简报 |
| `/stats` | 查看统计信息 |

## 配置说明

核心环境变量：

```bash
# 必需
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=sk-your_key  # 或 ANTHROPIC_API_KEY

# 可选
TIMEZONE=Asia/Shanghai
DAILY_BRIEFING_HOUR=9
MAX_PAPERS_PER_DAY=20
```

完整配置请参考 [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md)

## 运维支持

- **监控**: 日志监控、业务指标监控
- **备份**: 自动数据库备份
- **故障处理**: 常见问题排查指南
- **性能调优**: 数据库优化、日志轮转

详见 [OPERATIONS.md](OPERATIONS.md)

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 许可证

[MIT License](LICENSE)

## 联系方式

- 项目地址: [GitHub Repository]
- 问题反馈: [Issues]
- 邮件联系: [Email]

---

**注意**: 详细文档请查看项目根目录下的 `.md` 文件。
