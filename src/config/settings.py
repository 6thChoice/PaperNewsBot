"""应用配置管理."""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot Configuration
    telegram_bot_token: str = Field(default="", description="Telegram Bot Token")
    telegram_chat_id: str = Field(default="", description="Telegram Chat ID")
    telegram_proxy_url: Optional[str] = Field(None, description="Telegram Bot 代理 URL，如 socks5://127.0.0.1:7890")

    # AI API Keys
    openai_api_key: Optional[str] = Field(None, description="OpenAI API Key")
    openai_base_url: Optional[str] = Field(None, description="OpenAI API Base URL")
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API Key")
    anthropic_base_url: Optional[str] = Field(None, description="Anthropic API Base URL")
    model_name: Optional[str] = Field(None, description="LLM Name")

    # Database
    database_url: str = Field(
        "sqlite:///data/papernews.db", description="数据库连接URL"
    )

    # Application Settings
    debug: bool = Field(False, description="调试模式")
    log_level: str = Field("INFO", description="日志级别")
    timezone: str = Field("Asia/Shanghai", description="时区")

    # Crawler Settings
    arxiv_categories: str = Field(
        default="cs.AI,cs.CL,cs.CV,cs.LG",
        description="arXiv 论文分类（逗号分隔）",
    )
    arxiv_max_results: int = Field(50, description="arXiv 每次最大获取数量")
    openreview_conferences: str = Field(
        default="ICLR,NeurIPS,ICML",
        description="OpenReview 会议列表（逗号分隔）",
    )

    # Briefing Settings
    daily_briefing_hour: int = Field(9, description="每日简报发送小时")
    daily_briefing_minute: int = Field(0, description="每日简报发送分钟")
    max_papers_per_day: int = Field(10, description="每日最大论文数量")

    # User Interests
    user_interests: str = Field(
        default="machine learning,natural language processing,computer vision",
        description="用户兴趣关键词（逗号分隔）",
    )

    @property
    def arxiv_categories_list(self) -> List[str]:
        """获取 arXiv 分类列表."""
        return [item.strip() for item in self.arxiv_categories.split(",") if item.strip()]

    @property
    def openreview_conferences_list(self) -> List[str]:
        """获取 OpenReview 会议列表."""
        return [item.strip() for item in self.openreview_conferences.split(",") if item.strip()]

    @property
    def user_interests_list(self) -> List[str]:
        """获取用户兴趣列表."""
        return [item.strip() for item in self.user_interests.split(",") if item.strip()]

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """验证日志级别."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()


def get_settings() -> Settings:
    """获取配置实例."""
    return Settings()
