# PaperNews 架构设计文档

## 1. 系统架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              用户层 (Users)                              │
│                    Telegram App / Web / Mobile                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           接口网关 (Gateway)                             │
│                      Telegram Bot API / Webhook                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           应用层 (Application)                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  TelegramBot    │  │ TaskScheduler   │  │    Command Line         │  │
│  │  (交互处理器)    │  │  (任务调度器)    │  │    (命令行工具)          │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           服务层 (Services)                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │UserService   │ │PaperService  │ │BriefingService│ │AIService     │   │
│  │  用户服务     │ │  论文服务     │ │   简报服务     │ │  AI服务       │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                     │
│  │ArxivCrawler  │ │OpenReviewCrawler│ │BaseCrawler  │                     │
│  │ arXiv爬虫     │ │ OpenReview爬虫  │ │  爬虫基类     │                     │
│  └──────────────┘ └──────────────┘ └──────────────┘                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据层 (Data Layer)                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      SQLAlchemy ORM                              │   │
│  │              (支持 SQLite / PostgreSQL / MySQL)                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │   User   │ │  Paper   │ │ Briefing │ │Research  │ │UserBriefing│    │
│  │   用户表  │ │  论文表   │ │  简报表   │ │  Field   │ │ 用户简报关联│    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           外部服务 (External)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │  Telegram    │ │   arXiv      │ │ OpenReview   │ │ OpenAI/      │   │
│  │   API        │ │   API        │ │    API       │ │ Anthropic    │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. 核心模块说明

### 2.1 数据模型层 (Models)

```
┌─────────────────────────────────────────────────────────────────┐
│                         User (用户表)                            │
├─────────────────────────────────────────────────────────────────┤
│ 字段名              │ 类型      │ 说明                          │
├───────────────────┼─────────┼──────────────────────────────┤
│ id                │ INTEGER │ 主键，自增                      │
│ telegram_id       │ STRING  │ Telegram用户ID，唯一            │
│ username          │ STRING  │ 用户名，可为空                   │
│ first_name        │ STRING  │ 名，可为空                      │
│ last_name         │ STRING  │ 姓，可为空                      │
│ daily_paper_limit │ INTEGER │ 每日推送数量，默认10             │
│ is_active         │ BOOLEAN │ 是否启用推送，默认True           │
│ onboarding_completed│ BOOLEAN│ 是否完成初始设置，默认False     │
│ crawl_history_days│ INTEGER │ 历史爬取天数，默认7              │
│ created_at        │ DATETIME│ 创建时间                        │
│ updated_at        │ DATETIME│ 更新时间                        │
│ last_active_at    │ DATETIME│ 最后活跃时间                     │
└─────────────────────────────────────────────────────────────────┘

关系:
- research_fields: 多对多 → ResearchField
- user_briefings: 一对多 → UserBriefing
```

```
┌─────────────────────────────────────────────────────────────────┐
│                      ResearchField (研究领域表)                   │
├─────────────────────────────────────────────────────────────────┤
│ 字段名              │ 类型      │ 说明                          │
├───────────────────┼─────────┼──────────────────────────────┤
│ id                │ INTEGER │ 主键，自增                      │
│ name              │ STRING  │ 领域英文名，唯一                │
│ name_cn           │ STRING  │ 领域中文名                      │
│ description       │ TEXT    │ 描述                            │
│ arxiv_categories  │ TEXT    │ arXiv分类，逗号分隔             │
│ keywords          │ TEXT    │ 关键词，逗号分隔                │
│ is_active         │ BOOLEAN │ 是否启用，默认True              │
│ created_at        │ DATETIME│ 创建时间                        │
└─────────────────────────────────────────────────────────────────┘

预置领域:
1. machine_learning (机器学习) - cs.LG,cs.AI,stat.ML
2. nlp (自然语言处理) - cs.CL
3. computer_vision (计算机视觉) - cs.CV
4. robotics (机器人学) - cs.RO
5. reinforcement_learning (强化学习) - cs.LG,cs.AI,cs.MA
6. ai_safety (AI安全与对齐) - cs.AI,cs.LG,cs.CY
```

```
┌─────────────────────────────────────────────────────────────────┐
│                         Paper (论文表)                           │
├─────────────────────────────────────────────────────────────────┤
│ 字段名              │ 类型      │ 说明                          │
├───────────────────┼─────────┼──────────────────────────────┤
│ id                │ INTEGER │ 主键，自增                      │
│ external_id       │ STRING  │ 外部ID，唯一                    │
│ source            │ STRING  │ 来源: arxiv/openreview          │
│ title             │ TEXT    │ 标题                            │
│ authors           │ TEXT    │ 作者，逗号分隔                  │
│ abstract          │ TEXT    │ 摘要                            │
│ keywords          │ TEXT    │ 关键词，逗号分隔                │
│ publish_date      │ DATETIME│ 发布日期                        │
│ venue             │ STRING  │ 会议/期刊                       │
│ pdf_url           │ TEXT    │ PDF链接                         │
│ source_url        │ TEXT    │ 原文链接                        │
│ created_at        │ DATETIME│ 创建时间                        │
│ updated_at        │ DATETIME│ 更新时间                        │
└─────────────────────────────────────────────────────────────────┘

关系:
- briefings: 一对多 → Briefing
```

```
┌─────────────────────────────────────────────────────────────────┐
│                       Briefing (简报表)                          │
├─────────────────────────────────────────────────────────────────┤
│ 字段名              │ 类型      │ 说明                          │
├───────────────────┼─────────┼──────────────────────────────┤
│ id                │ INTEGER │ 主键，自增                      │
│ paper_id          │ INTEGER │ 外键 → Paper.id               │
│ content           │ TEXT    │ 简报内容（中文）                │
│ ai_model          │ STRING  │ 使用的AI模型                   │
│ created_at        │ DATETIME│ 创建时间                        │
└─────────────────────────────────────────────────────────────────┘

关系:
- paper: 多对一 → Paper
- user_briefings: 一对多 → UserBriefing
```

```
┌─────────────────────────────────────────────────────────────────┐
│                     UserBriefing (用户简报关联表)                 │
├─────────────────────────────────────────────────────────────────┤
│ 字段名              │ 类型      │ 说明                          │
├───────────────────┼─────────┼──────────────────────────────┤
│ id                │ INTEGER │ 主键，自增                      │
│ user_id           │ INTEGER │ 外键 → User.id                │
│ briefing_id       │ INTEGER │ 外键 → Briefing.id            │
│ is_sent           │ BOOLEAN │ 是否已发送，默认False           │
│ sent_at           │ DATETIME│ 发送时间                        │
│ is_read           │ BOOLEAN │ 是否已读，默认False             │
│ read_at           │ DATETIME│ 阅读时间                        │
│ is_interested     │ BOOLEAN │ 是否感兴趣，默认False           │
│ created_at        │ DATETIME│ 创建时间                        │
└─────────────────────────────────────────────────────────────────┘

说明:
- 记录每个用户的简报推送状态和阅读状态
- 支持同一简报推送给多个用户
```

### 2.2 服务层 (Services)

#### UserService - 用户服务

```python
class UserService:
    """用户服务类"""
    
    # 核心方法
    - init_research_fields()          # 初始化研究领域
    - get_or_create_user()            # 获取或创建用户
    - get_user_by_telegram_id()       # 通过Telegram ID获取用户
    - get_all_active_users()          # 获取所有活跃用户
    - set_user_research_fields()      # 设置用户研究领域
    - update_user_settings()          # 更新用户设置
    - get_research_fields()           # 获取所有研究领域
    - get_user_pending_briefings()    # 获取用户待发送简报
    - get_user_sent_briefings()       # 获取用户已发送简报
    - mark_briefing_sent()            # 标记简报已发送
    - mark_briefing_read()            # 标记简报已读
    - mark_briefing_interested()      # 标记简报感兴趣
```

#### PaperService - 论文服务

```python
class PaperService:
    """论文服务类"""
    
    # 核心方法
    - fetch_and_save_papers()         # 获取并保存论文
    - fetch_papers_for_user()         # 根据用户领域获取论文
    - _fetch_arxiv_papers()           # 获取arXiv论文
    - _fetch_openreview_papers()      # 获取OpenReview论文
    - _save_paper()                   # 保存论文到数据库
    - get_papers_for_briefing()       # 获取需要生成简报的论文
    - get_papers_by_ids()             # 通过ID列表获取论文
    - search_papers()                 # 搜索论文
    - get_recent_papers()             # 获取最近的论文
```

#### BriefingService - 简报服务

```python
class BriefingService:
    """简报服务类"""
    
    # 核心方法
    - generate_briefings()            # 生成简报
    - _get_pending_papers()           # 获取待生成简报的论文
    - _generate_single_briefing()     # 为单篇论文生成简报
    - create_user_briefings()         # 为用户创建简报关联
    - get_user_pending_briefings()    # 获取用户待发送简报
    - get_user_sent_briefings()       # 获取用户已发送简报
    - mark_user_briefing_sent()       # 标记用户简报已发送
    - mark_user_briefing_read()       # 标记用户简报已读
    - mark_user_briefing_interested() # 标记用户简报感兴趣
    - format_briefing_for_telegram()  # 格式化为Telegram消息
```

#### AIService - AI 服务

```python
class AIService:
    """AI服务类"""
    
    # 核心方法
    - generate_briefing()             # 生成论文简报
    - _call_openai()                  # 调用OpenAI API
    - _call_anthropic()               # 调用Anthropic API
    - _generate_fallback_summary()    # 生成Fallback简报
    - check_interest_match()          # 检查兴趣匹配度
```

### 2.3 爬虫层 (Crawlers)

```
BaseCrawler (基类)
    │
    ├── ArxivCrawler (arXiv爬虫)
    │   └── fetch_papers(categories, since)
    │       └── 使用 arxiv 库获取论文
    │
    └── OpenReviewCrawler (OpenReview爬虫)
        └── fetch_papers(venues, since)
            └── 使用 openreview-py 获取论文
```

### 2.4 机器人层 (Bot)

```
TelegramBot
    │
    ├── 命令处理器
    │   ├── cmd_start()           # /start - 注册/欢迎
    │   ├── cmd_help()            # /help - 帮助
    │   ├── cmd_settings()        # /settings - 查看设置
    │   ├── cmd_fields()          # /fields - 修改领域
    │   ├── cmd_limit()           # /limit - 修改每日数量
    │   ├── cmd_history()         # /history - 历史/设置天数
    │   ├── cmd_next()            # /next - 下一条简报
    │   ├── cmd_today()           # /today - 今日简报
    │   ├── cmd_list()            # /list - 所有简报
    │   ├── cmd_search()          # /search - 搜索论文
    │   ├── cmd_read()            # /read - 标记已读
    │   ├── cmd_interested()      # /interested - 标记感兴趣
    │   └── cmd_stats()           # /stats - 统计
    │
    ├── 回调处理器
    │   └── handle_callback()
    │       ├── field_{id}        # 领域选择
    │       ├── fields_done       # 完成选择
    │       ├── fields_cancel     # 取消选择
    │       ├── read_{id}         # 标记已读
    │       └── interested_{id}   # 标记感兴趣
    │
    └── 定时推送
        └── send_daily_briefings()
```

### 2.5 调度层 (Scheduler)

```
TaskScheduler
    │
    ├── 定时任务
    │   ├── _fetch_papers_job()       # 每天 06:00
    │   ├── _generate_briefings_job() # 每天 07:00
    │   └── _send_daily_briefings_job()# 每天 09:00 (可配置)
    │
    └── 手动任务
        ├── run_once("fetch")         # 手动爬取
        ├── run_once("generate")      # 手动生成
        ├── run_once("send")          # 手动发送
        └── run_once("all")           # 执行全部
```

## 3. 数据流转图

### 3.1 论文爬取流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   调度器     │────▶│PaperService │────▶│  ArxivCrawler│
│(06:00定时)  │     │             │     │             │
└─────────────┘     └─────────────┘     └──────┬──────┘
       │                                       │
       │         ┌─────────────┐              │
       │         │OpenReview   │◀─────────────┘
       │         │Crawler      │
       │         └──────┬──────┘
       │                │
       │                ▼
       │         ┌─────────────┐
       └────────▶│  Paper表    │
                 │  (保存论文)  │
                 └─────────────┘
```

### 3.2 简报生成流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   调度器     │────▶│BriefingService│───▶│  Paper表    │
│(07:00定时)  │     │             │     │(查询未生成)  │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  AIService  │
                    │(生成简报内容)│
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Briefing表  │
                    │ (保存简报)   │
                    └─────────────┘
```

### 3.3 用户推送流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   调度器     │────▶│BriefingService│───▶│   User表    │
│(09:00定时)  │     │             │     │(获取用户)    │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Briefing表  │
                    │(按领域筛选)  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │UserBriefing │
                    │(创建用户关联)│
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ TelegramBot │
                    │ (发送消息)   │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   用户      │
                    │ (接收简报)   │
                    └─────────────┘
```

## 4. 关键设计决策

### 4.1 为什么使用 UserBriefing 关联表？

**问题**: 为什么不直接在 Briefing 表记录发送状态？

**决策**:
- 一篇简报可以推送给多个用户
- 每个用户需要独立的阅读状态
- 支持同一简报在不同时间推送给不同用户

**方案**: 使用 UserBriefing 关联表记录 (user_id, briefing_id, is_sent, is_read)

### 4.2 为什么分离 Paper 和 Briefing？

**问题**: 为什么不把简报内容直接存在 Paper 表？

**决策**:
- 一篇论文可能需要多次生成简报（不同AI模型、不同语言）
- 简报生成是耗时操作，需要异步处理
- 支持重新生成简报而不影响论文数据

**方案**: 分离为两个表，通过外键关联

### 4.3 如何处理用户订阅领域？

**问题**: 如何根据用户领域筛选相关论文？

**决策**:
- 每个领域定义关键词列表
- 使用 SQL LIKE 查询匹配标题/摘要/关键词
- 论文分类通过 arXiv categories 确定

**方案**: 
```python
# 关键词匹配
keywords = ["machine learning", "deep learning", ...]
query.filter(
    or_(Paper.title.ilike(f"%{kw}%") for kw in keywords)
)
```

### 4.4 如何处理历史文章？

**问题**: 如何支持向前爬取历史文章？

**决策**:
- 每个用户可配置 `crawl_history_days`
- 调度器使用最大的历史天数统一爬取
- 所有论文存入数据库，用户按需获取

**方案**: 
```python
max_days = max(user.crawl_history_days for user in users)
papers = fetch_papers(days=max_days)
```

## 5. 扩展性设计

### 5.1 添加新的论文源

```python
# 1. 创建爬虫类
class NewCrawler(BaseCrawler):
    def fetch_papers(self, ...):
        # 实现爬取逻辑
        pass

# 2. 在 PaperService 中集成
class PaperService:
    def fetch_and_save_papers(self, ...):
        # 添加新爬虫调用
        new_papers = self.new_crawler.fetch_papers(...)
```

### 5.2 添加新的 AI 提供商

```python
# 1. 在 AIService 中添加新方法
class AIService:
    def _call_new_ai(self, prompt):
        # 调用新AI API
        pass
    
    def generate_briefing(self, ...):
        # 添加新AI选项
        if self.settings.new_ai_key:
            return self._call_new_ai(prompt)
```

### 5.3 支持多语言简报

```python
# 1. Briefing 表添加语言字段
class Briefing(Base):
    language = Column(String(10), default='zh')

# 2. AIService 支持多语言生成
class AIService:
    def generate_briefing(self, ..., language='zh'):
        prompt = self._get_prompt(language)
```

## 6. 性能优化

### 6.1 数据库优化

- **索引**: 在常用查询字段上建立索引
  - User.telegram_id
  - Paper.external_id + source
  - Briefing.paper_id
  - UserBriefing.user_id + is_sent

- **查询优化**: 使用 joinedload 预加载关联数据
  ```python
  query.options(joinedload(Briefing.paper))
  ```

### 6.2 爬取优化

- **去重**: 使用 external_id + source 唯一约束
- **批量**: 批量保存论文减少数据库操作
- **并发**: 使用 asyncio 并发爬取多个源

### 6.3 AI 生成优化

- **缓存**: 相同论文不重复生成
- **限流**: 控制 API 调用频率
- **Fallback**: API 失败时使用模板生成

## 7. 安全考虑

### 7.1 API Key 管理

- 使用环境变量存储敏感信息
- 不提交 .env 文件到版本控制
- 定期轮换 API Key

### 7.2 数据安全

- 用户数据隔离（通过 user_id）
- 数据库连接使用参数化查询防止 SQL 注入
- 定期备份数据库

### 7.3 访问控制

- Telegram Bot Token 验证
- 用户只能访问自己的数据
- 管理员功能需要额外验证

---

**文档版本**: v1.0  
**最后更新**: 2026-02-05
