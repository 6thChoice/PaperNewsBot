# PaperNews 运维手册

## 目录

1. [日常运维](#1-日常运维)
2. [监控与告警](#2-监控与告警)
3. [故障处理](#3-故障处理)
4. [数据备份与恢复](#4-数据备份与恢复)
5. [性能调优](#5-性能调优)
6. [升级维护](#6-升级维护)

---

## 1. 日常运维

### 1.1 检查系统状态

```bash
# 查看进程状态
ps aux | grep papernews

# 查看日志
tail -f logs/papernews.log

# 查看数据库大小
ls -lh data/papernews.db

# 查看系统资源使用
df -h
free -h
```

### 1.2 查看统计数据

```bash
# 使用 SQLite 命令行
sqlite3 data/papernews.db

# 常用查询
-- 用户数量
SELECT COUNT(*) FROM users;

-- 论文数量
SELECT COUNT(*) FROM papers;

-- 简报数量
SELECT COUNT(*) FROM briefings;

-- 今日新增论文
SELECT COUNT(*) FROM papers WHERE DATE(created_at) = DATE('now');

-- 活跃用户（7天内有活动）
SELECT COUNT(*) FROM users 
WHERE last_active_at > DATETIME('now', '-7 days');

-- 各用户简报统计
SELECT u.telegram_id, 
       COUNT(ub.id) as total,
       SUM(CASE WHEN ub.is_sent THEN 1 ELSE 0 END) as sent,
       SUM(CASE WHEN ub.is_read THEN 1 ELSE 0 END) as read
FROM users u
LEFT JOIN user_briefings ub ON u.id = ub.user_id
GROUP BY u.id;
```

### 1.3 手动触发任务

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

### 1.4 用户管理

```bash
# 查看所有用户
uv run python -c "
from src.services.user_service import UserService
service = UserService()
users = service.get_all_active_users()
for u in users:
    print(f'{u.telegram_id}: {u.username} - {len(u.research_fields)} fields')
"

# 禁用用户
uv run python -c "
from src.services.user_service import UserService
service = UserService()
service.update_user_settings('USER_ID', is_active=False)
print('User disabled')
"

# 修改用户设置
uv run python -c "
from src.services.user_service import UserService
service = UserService()
service.update_user_settings(
    'USER_ID',
    daily_paper_limit=20,
    crawl_history_days=14
)
print('Settings updated')
"
```

---

## 2. 监控与告警

### 2.1 日志监控

```bash
# 实时监控日志
tail -f logs/papernews.log | grep -E "(ERROR|WARNING|INFO)"

# 查看错误日志
grep ERROR logs/papernews.log | tail -20

# 统计今日错误数
grep "$(date +%Y-%m-%d)" logs/papernews.log | grep ERROR | wc -l
```

### 2.2 关键指标监控

创建监控脚本 `monitor.sh`:

```bash
#!/bin/bash

# 检查进程
if ! pgrep -f "python main.py scheduler" > /dev/null; then
    echo "[ALERT] PaperNews scheduler is not running!"
    # 发送告警（邮件/钉钉/Slack）
fi

# 检查数据库
DB_SIZE=$(stat -f%z data/papernews.db 2>/dev/null || stat -c%s data/papernews.db)
if [ $DB_SIZE -gt 1073741824 ]; then  # 1GB
    echo "[WARNING] Database size is over 1GB: $DB_SIZE bytes"
fi

# 检查磁盘空间
DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "[WARNING] Disk usage is over 80%: $DISK_USAGE%"
fi

# 检查日志文件大小
LOG_SIZE=$(stat -f%z logs/papernews.log 2>/dev/null || stat -c%s logs/papernews.log)
if [ $LOG_SIZE -gt 104857600 ]; then  # 100MB
    echo "[INFO] Rotating log file"
    mv logs/papernews.log logs/papernews.log.$(date +%Y%m%d)
    touch logs/papernews.log
fi
```

添加到定时任务:

```bash
chmod +x monitor.sh
# 每5分钟检查一次
echo "*/5 * * * * /path/to/PaperNews/monitor.sh" | crontab -
```

### 2.3 业务指标监控

```bash
# 创建监控脚本
uv run python -c "
from src.services.user_service import UserService
from src.services.briefing_service import BriefingService
from src.models import get_db_session
from datetime import datetime, timedelta

db = next(get_db_session())

# 统计指标
stats = {
    'total_users': db.query(User).count(),
    'active_users': db.query(User).filter(User.is_active == True).count(),
    'total_papers': db.query(Paper).count(),
    'total_briefings': db.query(Briefing).count(),
    'today_papers': db.query(Paper).filter(
        Paper.created_at >= datetime.utcnow().date()
    ).count(),
}

print('=== PaperNews Stats ===')
for k, v in stats.items():
    print(f'{k}: {v}')
"
```

---

## 3. 故障处理

### 3.1 机器人无响应

**症状**: Telegram 机器人不回复消息

**排查步骤**:

```bash
# 1. 检查进程
ps aux | grep papernews

# 2. 如果没有运行，重新启动
uv run python main.py scheduler

# 3. 检查 Token 是否有效
curl -s "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"

# 4. 查看日志
tail -50 logs/papernews.log | grep -i error
```

**常见原因**:
- Bot Token 失效或错误
- 网络连接问题
- 进程崩溃

### 3.2 论文爬取失败

**症状**: 没有新论文入库

**排查步骤**:

```bash
# 1. 手动测试爬取
uv run python -c "
from src.crawlers import ArxivCrawler
from datetime import datetime, timedelta

crawler = ArxivCrawler()
categories = ['cs.AI', 'cs.CL']
since = datetime.utcnow() - timedelta(days=1)

papers = list(crawler.fetch_papers(categories, since))
print(f'Fetched {len(papers)} papers')
"

# 2. 检查网络
curl -I https://export.arxiv.org/api/query

# 3. 检查日志
grep -i "arxiv\|crawler" logs/papernews.log | tail -20
```

**常见原因**:
- 网络问题
- arXiv API 限流
- 分类配置错误

### 3.3 简报生成失败

**症状**: 有论文但没有简报

**排查步骤**:

```bash
# 1. 检查 AI API Key
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# 2. 测试 AI 服务
uv run python -c "
from src.services.ai_service import AIService
service = AIService()
result = service.generate_briefing(
    title='Test Paper',
    authors='Test Author',
    abstract='This is a test abstract about machine learning.',
    venue='Test Venue'
)
print(result)
"

# 3. 检查日志
grep -i "ai\|briefing\|generate" logs/papernews.log | tail -20
```

**常见原因**:
- API Key 失效
- API 额度用完
- 网络超时

**Fallback 机制**:
- 系统会自动使用模板生成简报
- 检查日志中的 "Using fallback" 信息

### 3.4 数据库问题

**症状**: 数据库错误、数据丢失

**排查步骤**:

```bash
# 1. 检查数据库文件
ls -lh data/papernews.db
sqlite3 data/papernews.db ".tables"

# 2. 检查数据库完整性
sqlite3 data/papernews.db "PRAGMA integrity_check;"

# 3. 修复数据库（如有损坏）
sqlite3 data/papernews.db ".recover" | sqlite3 data/papernews.db.fixed
mv data/papernews.db data/papernews.db.bak
mv data/papernews.db.fixed data/papernews.db
```

### 3.5 推送失败

**症状**: 用户没有收到简报

**排查步骤**:

```bash
# 1. 检查待发送简报
uv run python -c "
from src.services.user_service import UserService
from src.services.briefing_service import BriefingService

user_service = UserService()
briefing_service = BriefingService()

users = user_service.get_all_active_users()
for user in users:
    pending = briefing_service.get_user_pending_briefings(user)
    print(f'{user.telegram_id}: {len(pending)} pending')
"

# 2. 手动发送测试
uv run python -c "
from src.bot.telegram_bot import TelegramBot
import asyncio

bot = TelegramBot()
async def test():
    await bot.initialize()
    await bot.application.bot.send_message(
        chat_id='YOUR_USER_ID',
        text='Test message'
    )
asyncio.run(test())
"
```

---

## 4. 数据备份与恢复

### 4.1 自动备份

创建备份脚本 `backup.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/path/to/backups"
DB_FILE="data/papernews.db"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p $BACKUP_DIR

# 备份数据库
cp $DB_FILE "$BACKUP_DIR/papernews_$DATE.db"

# 压缩备份
gzip "$BACKUP_DIR/papernews_$DATE.db"

# 保留最近30天的备份
find $BACKUP_DIR -name "papernews_*.db.gz" -mtime +30 -delete

# 备份配置文件
cp .env "$BACKUP_DIR/env_$DATE"
gzip "$BACKUP_DIR/env_$DATE"

echo "Backup completed: papernews_$DATE.db.gz"
```

添加到定时任务:

```bash
chmod +x backup.sh
# 每天凌晨2点备份
echo "0 2 * * * /path/to/PaperNews/backup.sh" | crontab -
```

### 4.2 手动备份

```bash
# 备份数据库
cp data/papernews.db "data/papernews_$(date +%Y%m%d).db.bak"

# 备份配置
cp .env "env_$(date +%Y%m%d).bak"

# 导出数据为 SQL
sqlite3 data/papernews.db ".dump" > "papernews_$(date +%Y%m%d).sql"
```

### 4.3 数据恢复

```bash
# 停止服务
pkill -f "python main.py"

# 恢复数据库
cp data/papernews.db.bak data/papernews.db

# 或从 SQL 导入
sqlite3 data/papernews.db < papernews_backup.sql

# 重启服务
uv run python main.py scheduler
```

### 4.4 数据迁移

```bash
# 导出特定表
sqlite3 data/papernews.db ".dump users" > users.sql
sqlite3 data/papernews.db ".dump papers" > papers.sql

# 导入到新数据库
sqlite3 new_database.db < users.sql
sqlite3 new_database.db < papers.sql
```

---

## 5. 性能调优

### 5.1 数据库优化

```bash
# 分析查询性能
sqlite3 data/papernews.db "ANALYZE;"

# 查看查询计划
sqlite3 data/papernews.db "EXPLAIN QUERY PLAN 
SELECT * FROM papers WHERE title LIKE '%machine learning%';"

# 优化数据库（VACUUM）
sqlite3 data/papernews.db "VACUUM;"

# 重建索引
sqlite3 data/papernews.db "REINDEX;"
```

### 5.2 日志轮转

```bash
# 使用 logrotate
cat > /etc/logrotate.d/papernews << 'EOF'
/path/to/PaperNews/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 user user
    postrotate
        /usr/bin/killall -HUP python
    endscript
}
EOF
```

### 5.3 内存优化

```bash
# 限制 Python 内存使用
ulimit -v 2097152  # 2GB 虚拟内存限制

# 使用 systemd 限制
# /etc/systemd/system/papernews.service
[Service]
MemoryLimit=2G
MemorySwapMax=0
```

### 5.4 并发优化

```python
# 在 config.py 中调整
class Settings:
    # 爬虫并发数
    CRAWLER_CONCURRENCY = 5
    
    # AI 生成并发数
    AI_CONCURRENCY = 3
    
    # 批量大小
    BATCH_SIZE = 50
```

---

## 6. 升级维护

### 6.1 代码更新

```bash
# 1. 备份当前版本
cp -r PaperNews PaperNews_$(date +%Y%m%d)

# 2. 拉取最新代码
git pull origin main

# 3. 更新依赖
uv sync

# 4. 数据库迁移（如有）
uv run python -c "from src.models import init_database; init_database()"

# 5. 重启服务
pkill -f "python main.py"
uv run python main.py scheduler
```

### 6.2 数据库迁移

```bash
# 查看当前版本
sqlite3 data/papernews.db "PRAGMA user_version;"

# 执行迁移脚本
uv run python -c "
from src.models import get_db_session

db = next(get_db_session())

# 示例：添加新字段
db.execute('ALTER TABLE users ADD COLUMN new_column TEXT')
db.commit()

# 更新版本号
db.execute('PRAGMA user_version = 2')
"
```

### 6.3 回滚操作

```bash
# 1. 停止服务
pkill -f "python main.py"

# 2. 恢复代码
cd PaperNews
git reset --hard HEAD~1  # 或指定版本
git checkout <commit_hash>

# 3. 恢复数据库
cp data/papernews.db.bak data/papernews.db

# 4. 重启服务
uv run python main.py scheduler
```

### 6.4 版本发布清单

```markdown
## 发布前检查
- [ ] 代码审查完成
- [ ] 测试通过
- [ ] 数据库备份完成
- [ ] 配置文件备份完成
- [ ] 更新日志编写完成

## 发布步骤
- [ ] 停止服务
- [ ] 部署新版本
- [ ] 执行数据库迁移
- [ ] 启动服务
- [ ] 验证功能正常
- [ ] 监控日志

## 发布后检查
- [ ] 机器人响应正常
- [ ] 论文爬取正常
- [ ] 简报生成正常
- [ ] 推送功能正常
- [ ] 用户反馈正常
```

---

## 附录

### A. 常用 SQL 查询

```sql
-- 查看表结构
.schema users

-- 查看索引
.indexes papers

-- 查看触发器
.triggers

-- 性能分析
.timer on
SELECT * FROM papers WHERE title LIKE '%AI%';
.timer off
```

### B. 系统要求

- **OS**: Linux/macOS/Windows
- **Python**: 3.9+
- **内存**: 最低 512MB，推荐 1GB+
- **磁盘**: 最低 1GB，推荐 5GB+
- **网络**: 需要访问 Telegram API、arXiv、OpenReview、OpenAI/Anthropic

### C. 联系信息

- 项目负责人: [Name]
- 技术负责人: [Name]
- 运维邮箱: [Email]
- 紧急联系: [Phone]

---

**文档版本**: v1.0  
**最后更新**: 2026-02-05
