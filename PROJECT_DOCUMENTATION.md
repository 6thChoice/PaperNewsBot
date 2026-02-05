# PaperNews 项目交接文档

## 项目概述

PaperNews 是一个学术论文追踪与简报生成系统，通过爬取 arXiv 和 OpenReview 的最新论文，利用 AI 生成中文简报，并通过 Telegram 机器人推送给订阅用户。

### 核心功能

1. **多源论文爬取**：支持 arXiv 和 OpenReview
2. **AI 简报生成**：使用 OpenAI/Anthropic API 生成论文中文摘要
3. **用户管理系统**：支持多用户、订阅领域个性化配置
4. **差异化推送**：根据用户订阅领域推送相关论文
5. **历史文章支持**：可配置向前爬取历史文章
6. **阅读状态追踪**：记录用户已读、感兴趣的论文

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        数据层 (Data Layer)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │    Paper     │  │   Briefing   │  │      User        │  │
│  │    论文表     │  │    简报表     │  │     用户表        │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ResearchField │  │ UserBriefing │  │    UserState     │  │
│  │   研究领域表  │  │  用户简报关联  │  │   用户状态(旧)    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      服务层 (Service Layer)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │PaperService  │  │BriefingService│  │  UserService     │  │
│  │  论文服务     │  │   简报服务     │  │   用户服务        │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │  AIService   │  │   Crawlers   │                        │
│  │   AI服务      │  │   爬虫模块     │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      接口层 (Interface Layer)                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              TelegramBot (Telegram 机器人)            │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              TaskScheduler (任务调度器)               │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 代码运行流程

### 1. 系统启动流程

```
main.py
    │
    ├── 加载配置 (config.py)
    │   └── 从 .env 文件读取环境变量
    │
    ├── 初始化数据库 (models/database.py)
    │   └── 创建所有表结构
    │
    ├── 初始化研究领域 (user_service.py)
    │   └── 创建默认的6个研究领域
    │
    └── 启动调度器 (scheduler.py)
        ├── 启动 Telegram 机器人
        └── 配置定时任务
```

### 2. 论文爬取流程

```
TaskScheduler._fetch_papers_job()
    │
    ├── 获取所有活跃用户
    │   └── UserService.get_all_active_users()
    │
    ├── 收集所有需要爬取的分类
    │   └── 遍历用户的 research_fields
    │       └── 获取每个领域的 arxiv_categories
    │
    ├── 确定最大历史天数
    │   └── max(user.crawl_history_days)
    │
    └── 执行爬取
        ├── ArxivCrawler.fetch_papers(categories, since)
        │   └── 使用 arxiv API 获取论文
        │
        ├── OpenReviewCrawler.fetch_papers(venues, since)
        │   └── 使用 OpenReview API 获取论文
        │
        └── PaperService._save_paper(metadata)
            └── 保存到 Paper 表（去重检查）
```

### 3. 简报生成流程

```
TaskScheduler._generate_briefings_job()
    │
    ├── 获取所有活跃用户
    │
    ├── 收集所有研究领域
    │
    └── BriefingService.generate_briefings(research_fields)
        │
        ├── 查询没有简报的论文
        │   └── PaperService._get_pending_papers()
        │       └── 根据关键词筛选相关论文
        │
        └── 为每篇论文生成简报
            └── BriefingService._generate_single_briefing(paper)
                │
                ├── AIService.generate_briefing()
                │   ├── 调用 OpenAI API (优先)
                │   ├── 或调用 Anthropic API
                │   └── 或使用 Fallback 模板
                │
                └── 保存到 Briefing 表
```

### 4. 用户推送流程

```
TaskScheduler._send_daily_briefings_job()
    │
    └── TelegramBot.send_daily_briefings()
        │
        ├── 遍历所有活跃用户
        │   │
        │   ├── BriefingService.create_user_briefings(user)
        │   │   └── 为用户分配匹配的简报
        │   │       └── 根据用户领域关键词筛选
        │   │       └── 按时间倒序排列
        │   │
        │   ├── BriefingService.get_user_pending_briefings(user)
        │   │   └── 查询用户的待发送简报
        │   │
        │   └── 发送简报（限制数量）
        │       ├── 按 user.daily_paper_limit 限制
        │       ├── 格式化消息
        │       ├── 添加操作按钮（已读/感兴趣）
        │       └── 标记为已发送
        │
        └── 记录发送日志
```

### 5. 用户交互流程

```
用户发送 /start
    │
    └── TelegramBot.cmd_start()
        │
        ├── UserService.get_or_create_user()
        │   └── 创建或更新用户信息
        │
        └── 检查 onboarding_completed
            ├── False: 启动领域选择流程
            │   └── _start_field_selection()
            │       └── 显示交互式键盘
            │
            └── True: 显示欢迎回来消息

用户选择领域
    │
    └── TelegramBot.handle_callback()
        ├── field_{id}: 切换选择状态
        ├── fields_done: 保存选择
        │   └── UserService.set_user_research_fields()
        └── fields_cancel: 取消

用户发送 /next
    │
    └── TelegramBot.cmd_next()
        ├── 获取用户待发送简报
        ├── 如果没有，尝试创建
        └── 发送第一条并标记已发送

用户发送 /history
    │
    └── TelegramBot.cmd_history()
        ├── 有参数: 修改历史爬取天数
        └── 无参数: 显示历史简报
```

---

## 数据流程

### 数据模型关系图

```
┌────────────────────────────────────────────────────────────────┐
│                           User (用户)                           │
├────────────────────────────────────────────────────────────────┤
│ id (PK)          │ 用户ID                                        │
│ telegram_id (UK) │ Telegram 用户ID                               │
│ username         │ 用户名                                        │
│ first_name       │ 名                                           │
│ last_name        │ 姓                                           │
│ daily_paper_limit│ 每日推送数量 (默认10)                          │
│ is_active        │ 是否启用推送 (默认True)                        │
│ onboarding_completed│ 是否完成初始设置 (默认False)                 │
│ crawl_history_days│ 历史爬取天数 (默认7)                          │
└────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  ResearchField   │ │   UserBriefing   │ │    UserState     │
│   (研究领域)      │ │   (用户简报关联)  │ │   (用户状态-旧)   │
├──────────────────┤ ├──────────────────┤ ├──────────────────┤
│ id (PK)          │ │ id (PK)          │ │ id (PK)          │
│ name (UK)        │ │ user_id (FK)     │ │ user_id          │
│ name_cn          │ │ briefing_id (FK) │ │ paper_id (FK)    │
│ description      │ │ is_sent          │ │ is_read          │
│ arxiv_categories │ │ sent_at          │ │ is_interested    │
│ keywords         │ │ is_read          │ │ read_at          │
│ is_active        │ │ read_at          │ │ updated_at       │
└──────────────────┘ │ is_interested    │ └──────────────────┘
         ▲           └──────────────────┘
         │                    │
         │                    ▼
         │           ┌──────────────────┐
         │           │     Briefing     │
         │           │     (简报)        │
         │           ├──────────────────┤
         │           │ id (PK)          │
         │           │ paper_id (FK)    │
         │           │ content          │
         │           │ ai_model         │
         │           │ created_at       │
         │           └──────────────────┘
         │                    │
         │                    ▼
         │           ┌──────────────────┐
         │           │      Paper       │
         │           │     (论文)        │
         │           ├──────────────────┤
         │           │ id (PK)          │
         │           │ external_id (UK) │
         │           │ source           │
         │           │ title            │
         │           │ authors          │
         │           │ abstract         │
         │           │ keywords         │
         │           │ publish_date     │
         │           │ venue            │
         │           │ pdf_url          │
         │           │ source_url       │
         │           └──────────────────┘
         │
         │ 多对多关联表: user_research_fields
         │
         └──────────────────────────────────┘
```

### 数据流向

```
1. 论文数据流:
   Crawlers → PaperService → Paper表

2. 简报数据流:
   Paper表 + AIService → BriefingService → Briefing表

3. 用户简报数据流:
   Briefing表 + User表 → BriefingService.create_user_briefings() → UserBriefing表

4. 推送数据流:
   UserBriefing表 → TelegramBot → 用户
```

---

## 配置参数设置

### 环境变量配置 (.env)

```bash
# ============================================
# 必需配置
# ============================================

# Telegram Bot Token (从 @BotFather 获取)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# ============================================
# AI 服务配置 (至少配置一个)
# ============================================

# OpenAI API Key (推荐)
OPENAI_API_KEY=sk-your_openai_api_key_here

# 或 Anthropic API Key
ANTHROPIC_API_KEY=sk-your_anthropic_api_key_here

# ============================================
# 可选配置
# ============================================

# 数据库配置 (默认使用 SQLite)
DATABASE_URL=sqlite:///data/papernews.db

# 时区设置
TIMEZONE=Asia/Shanghai

# 每日简报推送时间 (24小时制)
DAILY_BRIEFING_HOUR=9
DAILY_BRIEFING_MINUTE=0

# arXiv 爬取配置
ARXIV_MAX_RESULTS=100
ARXIV_CATEGORIES=cs.AI,cs.CL,cs.CV,cs.LG,cs.RO,stat.ML

# OpenReview 会议配置
OPENREVIEW_CONFERENCES=ICLR,NeurIPS,ICML

# 每日最大论文数
MAX_PAPERS_PER_DAY=20
```

### 配置参数说明

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `TELEGRAM_BOT_TOKEN` | string | 必填 | Telegram Bot Token |
| `OPENAI_API_KEY` | string | 可选 | OpenAI API Key |
| `ANTHROPIC_API_KEY` | string | 可选 | Anthropic API Key |
| `DATABASE_URL` | string | sqlite | 数据库连接URL |
| `TIMEZONE` | string | Asia/Shanghai | 时区 |
| `DAILY_BRIEFING_HOUR` | int | 9 | 每日推送小时 |
| `DAILY_BRIEFING_MINUTE` | int | 0 | 每日推送分钟 |
| `ARXIV_MAX_RESULTS` | int | 100 | arXiv最大结果数 |
| `ARXIV_CATEGORIES` | string | cs.AI,... | arXiv分类 |
| `OPENREVIEW_CONFERENCES` | string | ICLR,... | OpenReview会议 |
| `MAX_PAPERS_PER_DAY` | int | 20 | 每日最大论文数 |

---

## Telegram 机器人配置方法

### 1. 创建 Telegram Bot

1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 命令
3. 按提示输入机器人名称和用户名
4. 保存获得的 **Bot Token**

### 2. 配置环境变量

将 Bot Token 写入 `.env` 文件：

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

### 3. 启动机器人

```bash
# 使用 uv 运行
uv run python main.py bot

# 或使用调度器模式（自动启动机器人）
uv run python main.py scheduler
```

### 4. 机器人命令列表

在 @BotFather 中设置命令菜单：

```
start - 开始使用机器人（注册/欢迎）
help - 显示帮助信息
settings - 查看当前设置
fields - 修改研究领域
limit - 修改每日推送数量
history - 查看历史简报或修改历史爬取天数
next - 获取下一条待读简报
today - 查看今日待读简报
list - 查看所有简报
search - 搜索论文
read - 标记简报为已读
interested - 标记感兴趣的简报
stats - 查看统计信息
```

设置方法：
1. 向 @BotFather 发送 `/setcommands`
2. 选择你的机器人
3. 粘贴上面的命令列表

---

## 项目结构

```
PaperNews/
├── .env                          # 环境变量配置
├── pyproject.toml                # 项目依赖配置
├── readme.md                     # 项目说明
├── PROJECT_DOCUMENTATION.md      # 本文档
│
├── data/                         # 数据目录
│   └── papernews.db              # SQLite 数据库
│
├── src/                          # 源代码
│   ├── __init__.py
│   ├── config.py                 # 配置管理
│   ├── main.py                   # 程序入口
│   │
│   ├── models/                   # 数据模型
│   │   ├── __init__.py
│   │   └── database.py           # 数据库模型定义
│   │
│   ├── crawlers/                 # 爬虫模块
│   │   ├── __init__.py
│   │   ├── base.py               # 爬虫基类
│   │   ├── arxiv_crawler.py      # arXiv 爬虫
│   │   └── openreview_crawler.py # OpenReview 爬虫
│   │
│   ├── services/                 # 服务层
│   │   ├── __init__.py
│   │   ├── ai_service.py         # AI 简报生成
│   │   ├── paper_service.py      # 论文服务
│   │   ├── briefing_service.py   # 简报服务
│   │   └── user_service.py       # 用户服务
│   │
│   ├── bot/                      # Telegram 机器人
│   │   ├── __init__.py
│   │   └── telegram_bot.py       # 机器人实现
│   │
│   └── scheduler.py              # 任务调度器
│
└── tests/                        # 测试文件
    ├── test_user_system.py
    └── test_complete_system.py
```

---

## 部署指南

### 1. 环境准备

```bash
# 克隆项目
git clone <repository_url>
cd PaperNews

# 安装依赖
uv sync

# 创建环境变量文件
cp .env.example .env
# 编辑 .env 文件，填入配置
```

### 2. 数据库初始化

```bash
# 首次运行会自动创建数据库
uv run python -c "from src.models import init_database; init_database()"
```

### 3. 运行模式

#### 模式一：仅运行机器人（前台交互）

```bash
uv run python main.py bot
```

#### 模式二：仅运行调度器（后台任务）

```bash
uv run python main.py scheduler
```

#### 模式三：手动执行任务

```bash
# 爬取论文
uv run python main.py fetch

# 生成简报
uv run python main.py generate

# 发送简报
uv run python main.py send

# 执行所有任务
uv run python main.py run-all
```

### 4. 生产环境部署

推荐使用 systemd 或 Docker 部署：

#### Systemd 服务配置

创建 `/etc/systemd/system/papernews.service`：

```ini
[Unit]
Description=PaperNews Academic Paper Tracker
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/PaperNews
ExecStart=/usr/local/bin/uv run python main.py scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable papernews
sudo systemctl start papernews
```

---

## 常见问题排查

### 1. 数据库问题

**问题**: 数据库表结构变更后报错

**解决**:
```bash
# 删除旧数据库重新初始化
rm data/papernews.db
uv run python -c "from src.models import init_database; init_database()"
```

### 2. AI 服务问题

**问题**: AI 简报生成失败

**排查**:
- 检查 `.env` 中 API Key 是否正确
- 检查 API 额度是否充足
- 查看日志中的具体错误信息

**Fallback**: 系统会自动使用模板生成简报

### 3. Telegram 机器人问题

**问题**: 机器人无响应

**排查**:
- 检查 `TELEGRAM_BOT_TOKEN` 是否正确
- 检查网络连接
- 查看日志: `tail -f logs/papernews.log`

### 4. 论文爬取问题

**问题**: 爬取不到论文

**排查**:
- 检查 arXiv/OpenReview 服务是否正常
- 检查网络连接
- 调整 `crawl_history_days` 参数

---

## 扩展开发指南

### 添加新的研究领域

编辑 `src/services/user_service.py`：

```python
DEFAULT_RESEARCH_FIELDS = [
    # ... 现有领域 ...
    {
        "name": "new_field",
        "name_cn": "新领域",
        "description": "Description",
        "arxiv_categories": "cs.XX,cs.YY",
        "keywords": "keyword1,keyword2",
    },
]
```

重启服务后自动创建。

### 添加新的爬虫源

1. 在 `src/crawlers/` 创建新的爬虫类
2. 继承 `BaseCrawler`
3. 实现 `fetch_papers()` 方法
4. 在 `PaperService` 中集成

### 添加新的机器人命令

1. 在 `TelegramBot` 类中添加处理方法
2. 在 `initialize()` 中注册命令处理器
3. 在 @BotFather 中更新命令列表

---

## 联系与支持

如有问题，请检查：
1. 日志文件：`logs/papernews.log`
2. 数据库状态：`data/papernews.db`
3. 环境变量配置：`.env`

---

**文档版本**: v1.0  
**最后更新**: 2026-02-05  
**项目地址**: [PaperNews Repository]
