"""日志配置."""

import sys
from pathlib import Path

from loguru import logger

from src.config import get_settings


def setup_logger():
    """配置日志."""
    settings = get_settings()

    # 移除默认处理器
    logger.remove()

    # 添加控制台处理器
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    # 添加文件处理器
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger.add(
        log_dir / "papernews.log",
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="1 day",
        retention="7 days",
        encoding="utf-8",
    )

    return logger
