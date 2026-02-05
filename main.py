"""PaperNews 主程序入口."""

import asyncio
import argparse
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.logger import setup_logger
from src.models import init_database
from src.scheduler import TaskScheduler, run_scheduler


async def run_fetch():
    """运行论文爬取任务."""
    from src.services.paper_service import PaperService
    from src.models import get_db_session
    from src.models.database import Paper

    logger = setup_logger()
    logger.info("Running fetch papers task...")

    init_database()

    # 获取当前数据库中的论文数量
    db = next(get_db_session())
    existing_count = db.query(Paper).count()
    logger.info(f"Current papers in database: {existing_count}")

    service = PaperService()
    papers = service.fetch_and_save_papers(days=1)

    logger.info(f"Fetched and saved {len(papers)} papers")

    if len(papers) == 0 and existing_count > 0:
        print(f"ℹ️ 未发现新论文（数据库已有 {existing_count} 篇，去重过滤）")
    else:
        print(f"✅ 成功获取并保存 {len(papers)} 篇论文")


async def run_generate():
    """运行简报生成任务."""
    from src.services.briefing_service import BriefingService

    logger = setup_logger()
    logger.info("Running generate briefings task...")

    init_database()
    service = BriefingService()
    briefings = service.generate_briefings()

    logger.info(f"Generated {len(briefings)} briefings")
    print(f"✅ 成功生成 {len(briefings)} 条简报")


async def run_send():
    """运行发送简报任务."""
    from src.bot.telegram_bot import TelegramBot

    logger = setup_logger()
    logger.info("Running send briefings task...")

    init_database()
    bot = TelegramBot()
    await bot.initialize()
    await bot.send_daily_briefings()
    await bot.stop()

    logger.info("Briefings sent successfully")
    print("✅ 简报发送完成")


async def run_bot():
    """运行 Telegram 机器人."""
    from src.bot.telegram_bot import TelegramBot

    logger = setup_logger()
    logger.info("Starting Telegram bot...")

    init_database()
    bot = TelegramBot()
    await bot.start()

    print("🤖 Telegram 机器人已启动，按 Ctrl+C 停止")

    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        await bot.stop()
        print("\n👋 机器人已停止")


async def run_all():
    """运行完整流程（爬取、生成、发送）."""
    logger = setup_logger()
    logger.info("Running complete workflow...")

    init_database()

    # 爬取论文
    print("📥 正在爬取论文...")
    from src.services.paper_service import PaperService
    paper_service = PaperService()
    papers = paper_service.fetch_and_save_papers(days=1)
    print(f"✅ 获取 {len(papers)} 篇论文")

    # 生成简报
    print("📝 正在生成简报...")
    from src.services.briefing_service import BriefingService
    briefing_service = BriefingService()
    briefings = briefing_service.generate_briefings(papers=papers)
    print(f"✅ 生成 {len(briefings)} 条简报")

    # 发送简报
    if briefings:
        print("📤 正在发送简报...")
        from src.bot.telegram_bot import TelegramBot
        bot = TelegramBot()
        await bot.initialize()
        await bot.send_daily_briefings()
        await bot.stop()
        print("✅ 简报发送完成")
    else:
        print("ℹ️ 没有简报需要发送")


def main():
    """主函数."""
    parser = argparse.ArgumentParser(
        description="PaperNews - 学术论文追踪与简报系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py scheduler    # 启动定时任务调度器
  python main.py fetch        # 手动爬取论文
  python main.py generate     # 手动生成简报
  python main.py send         # 手动发送简报
  python main.py bot          # 启动 Telegram 机器人
  python main.py all          # 运行完整流程
        """,
    )

    parser.add_argument(
        "command",
        choices=["scheduler", "fetch", "generate", "send", "bot", "all"],
        help="要执行的命令",
    )

    args = parser.parse_args()

    # 设置日志
    setup_logger()

    # 执行命令
    if args.command == "scheduler":
        asyncio.run(run_scheduler())
    elif args.command == "fetch":
        asyncio.run(run_fetch())
    elif args.command == "generate":
        asyncio.run(run_generate())
    elif args.command == "send":
        asyncio.run(run_send())
    elif args.command == "bot":
        asyncio.run(run_bot())
    elif args.command == "all":
        asyncio.run(run_all())


if __name__ == "__main__":
    main()
