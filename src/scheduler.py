"""定时任务调度器."""

import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.config import get_settings
from src.models import init_database
from src.services.paper_service import PaperService
from src.services.briefing_service import BriefingService
from src.services.user_service import UserService
from src.bot.telegram_bot import TelegramBot


class TaskScheduler:
    """任务调度器类."""

    def __init__(self):
        """初始化调度器."""
        self.settings = get_settings()
        self.scheduler = AsyncIOScheduler(timezone=self.settings.timezone)
        self.paper_service = PaperService()
        self.briefing_service = BriefingService()
        self.user_service = UserService()
        self.telegram_bot = TelegramBot()

    async def initialize(self):
        """初始化调度器和机器人."""
        # 初始化数据库
        init_database()

        # 初始化研究领域
        self.user_service.init_research_fields()

        # 初始化并启动机器人（启动消息轮询）
        await self.telegram_bot.initialize()
        await self.telegram_bot.start()

        # 配置定时任务
        self._setup_jobs()

        logger.info("Task scheduler initialized")

    def _setup_jobs(self):
        """配置定时任务."""
        # 每天早上爬取论文
        self.scheduler.add_job(
            self._fetch_papers_job,
            CronTrigger(hour=6, minute=0),
            id="fetch_papers",
            name="Fetch daily papers",
            replace_existing=True,
        )

        # 生成简报
        self.scheduler.add_job(
            self._generate_briefings_job,
            CronTrigger(hour=7, minute=0),
            id="generate_briefings",
            name="Generate briefings",
            replace_existing=True,
        )

        # 发送每日简报
        self.scheduler.add_job(
            self._send_daily_briefings_job,
            CronTrigger(
                hour=self.settings.daily_briefing_hour,
                minute=self.settings.daily_briefing_minute,
            ),
            id="send_briefings",
            name="Send daily briefings",
            replace_existing=True,
        )

        logger.info(
            f"Scheduled daily briefing at {self.settings.daily_briefing_hour:02d}:{self.settings.daily_briefing_minute:02d}"
        )

    async def _fetch_papers_job(self):
        """爬取论文任务 - 为每个用户爬取其订阅领域的历史文章."""
        logger.info("Starting paper fetching job")
        try:
            # 获取所有活跃用户
            users = self.user_service.get_all_active_users()
            logger.info(f"Fetching papers for {len(users)} users")
            
            # 收集所有需要爬取的分类和天数
            all_categories = set()
            max_days = 1
            
            for user in users:
                if user.research_fields:
                    for field in user.research_fields:
                        all_categories.update(field.get_arxiv_categories_list())
                    # 使用最大的历史天数
                    max_days = max(max_days, user.crawl_history_days)
            
            if all_categories:
                # 爬取论文（使用最大的历史天数）
                papers = self.paper_service.fetch_and_save_papers(
                    days=max_days,
                    categories=list(all_categories)
                )
                logger.info(f"Fetched and saved {len(papers)} papers (days={max_days})")
            else:
                logger.warning("No research fields configured for any user")
                
        except Exception as e:
            logger.error(f"Error in fetch papers job: {e}")

    async def _generate_briefings_job(self):
        """生成简报任务 - 为所有用户的订阅领域生成简报."""
        logger.info("Starting briefing generation job")
        try:
            # 获取所有活跃用户
            users = self.user_service.get_all_active_users()
            
            # 收集所有研究领域
            all_fields = set()
            for user in users:
                for field in user.research_fields:
                    all_fields.add(field)
            
            if all_fields:
                # 为所有领域生成简报
                briefings = self.briefing_service.generate_briefings(
                    research_fields=list(all_fields)
                )
                logger.info(f"Generated {len(briefings)} briefings for all fields")
            else:
                logger.warning("No research fields configured")
                
        except Exception as e:
            logger.error(f"Error in generate briefings job: {e}")

    async def _send_daily_briefings_job(self):
        """发送每日简报任务 - 为每个用户发送其订阅领域的简报."""
        logger.info("Starting daily briefing sending job")
        try:
            await self.telegram_bot.send_daily_briefings()
            logger.info("Daily briefings sent successfully")
        except Exception as e:
            logger.error(f"Error in send daily briefings job: {e}")

    async def run_once(self, task_type: str = "all"):
        """手动运行一次任务.

        Args:
            task_type: 任务类型 (fetch, generate, send, all)
        """
        logger.info(f"Running task once: {task_type}")

        if task_type in ("all", "fetch"):
            await self._fetch_papers_job()

        if task_type in ("all", "generate"):
            await self._generate_briefings_job()

        if task_type in ("all", "send"):
            await self._send_daily_briefings_job()

    def start(self):
        """启动调度器."""
        self.scheduler.start()
        logger.info("Task scheduler started")

    def shutdown(self):
        """关闭调度器."""
        self.scheduler.shutdown()
        logger.info("Task scheduler shutdown")


async def run_scheduler():
    """运行调度器的主函数."""
    scheduler = TaskScheduler()
    await scheduler.initialize()
    scheduler.start()

    try:
        # 保持运行
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        scheduler.shutdown()
        await scheduler.telegram_bot.stop()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
