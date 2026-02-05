"""数据库模型定义."""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Generator, Optional, List

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    Table,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from loguru import logger

from src.config import get_settings

Base = declarative_base()


# 用户和领域的多对多关联表
user_research_fields = Table(
    'user_research_fields',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('field_id', Integer, ForeignKey('research_fields.id'), primary_key=True)
)


class PaperSource(str, PyEnum):
    """论文来源枚举."""

    ARXIV = "arxiv"
    OPENREVIEW = "openreview"


class ResearchField(Base):
    """研究领域模型."""

    __tablename__ = "research_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    name_cn = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    arxiv_categories = Column(Text, nullable=True)  # 逗号分隔的 arXiv 分类
    keywords = Column(Text, nullable=True)  # 逗号分隔的关键词
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关联关系
    users = relationship("User", secondary=user_research_fields, back_populates="research_fields")

    def __repr__(self) -> str:
        return f"<ResearchField(id={self.id}, name='{self.name}')>"

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": self.id,
            "name": self.name,
            "name_cn": self.name_cn,
            "description": self.description,
            "arxiv_categories": self.arxiv_categories,
            "keywords": self.keywords,
            "is_active": self.is_active,
        }

    def get_arxiv_categories_list(self) -> List[str]:
        """获取 arXiv 分类列表."""
        if self.arxiv_categories:
            return [cat.strip() for cat in self.arxiv_categories.split(",") if cat.strip()]
        return []

    def get_keywords_list(self) -> List[str]:
        """获取关键词列表."""
        if self.keywords:
            return [kw.strip() for kw in self.keywords.split(",") if kw.strip()]
        return []


class User(Base):
    """用户模型."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(String(100), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    
    # 用户设置
    daily_paper_limit = Column(Integer, default=10, nullable=False)  # 每日推送数量限制
    is_active = Column(Boolean, default=True, nullable=False)  # 是否启用推送
    onboarding_completed = Column(Boolean, default=False, nullable=False)  # 是否完成初始设置
    
    # 历史文章爬取设置
    crawl_history_days = Column(Integer, default=7, nullable=False)  # 向前爬取多少天的历史文章
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关联关系
    research_fields = relationship("ResearchField", secondary=user_research_fields, back_populates="users")
    user_briefings = relationship("UserBriefing", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id='{self.telegram_id}', username='{self.username}')>"

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "daily_paper_limit": self.daily_paper_limit,
            "is_active": self.is_active,
            "onboarding_completed": self.onboarding_completed,
            "crawl_history_days": self.crawl_history_days,
            "research_fields": [field.to_dict() for field in self.research_fields],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Paper(Base):
    """论文模型."""

    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), unique=True, nullable=False, index=True)
    source = Column(String(50), nullable=False, index=True)
    title = Column(Text, nullable=False)
    authors = Column(Text, nullable=False)
    abstract = Column(Text, nullable=False)
    keywords = Column(Text, nullable=True)
    publish_date = Column(DateTime, nullable=True, index=True)
    venue = Column(String(255), nullable=True)
    pdf_url = Column(Text, nullable=True)
    source_url = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联关系
    briefings = relationship("Briefing", back_populates="paper", cascade="all, delete-orphan")
    user_states = relationship("UserState", back_populates="paper", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_papers_source_external_id", "source", "external_id"),
    )

    def __repr__(self) -> str:
        return f"<Paper(id={self.id}, title='{self.title[:50]}...')>"

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": self.id,
            "external_id": self.external_id,
            "source": self.source,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "publish_date": self.publish_date.isoformat() if self.publish_date else None,
            "venue": self.venue,
            "pdf_url": self.pdf_url,
            "source_url": self.source_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Briefing(Base):
    """简报模型."""

    __tablename__ = "briefings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    ai_model = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关联关系
    paper = relationship("Paper", back_populates="briefings")
    user_briefings = relationship("UserBriefing", back_populates="briefing", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Briefing(id={self.id}, paper_id={self.paper_id})>"

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "content": self.content,
            "ai_model": self.ai_model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "paper": self.paper.to_dict() if self.paper else None,
        }


class UserBriefing(Base):
    """用户简报关联模型（记录推送状态）."""

    __tablename__ = "user_briefings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    briefing_id = Column(Integer, ForeignKey("briefings.id"), nullable=False, index=True)
    is_sent = Column(Boolean, default=False, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)
    is_interested = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关联关系
    user = relationship("User", back_populates="user_briefings")
    briefing = relationship("Briefing", back_populates="user_briefings")

    __table_args__ = (
        Index("ix_user_briefings_user_briefing", "user_id", "briefing_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserBriefing(id={self.id}, user_id='{self.user_id}', briefing_id={self.briefing_id}, is_sent={self.is_sent})>"

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "briefing_id": self.briefing_id,
            "is_sent": self.is_sent,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "is_interested": self.is_interested,
        }


class UserState(Base):
    """用户状态模型（保留用于向后兼容）."""

    __tablename__ = "user_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    briefing_id = Column(Integer, ForeignKey("briefings.id"), nullable=True, index=True)
    is_read = Column(Boolean, default=False, nullable=False)
    is_interested = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关联关系
    paper = relationship("Paper", back_populates="user_states")

    __table_args__ = (
        Index("ix_user_states_user_paper", "user_id", "paper_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserState(id={self.id}, user_id='{self.user_id}', paper_id={self.paper_id})>"

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "paper_id": self.paper_id,
            "briefing_id": self.briefing_id,
            "is_read": self.is_read,
            "is_interested": self.is_interested,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# 数据库引擎和会话工厂
_engine = None
_SessionLocal = None


def get_engine():
    """获取数据库引擎."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            echo=settings.debug,
            connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
        )
    return _engine


def get_session_local():
    """获取会话工厂."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def init_database():
    """初始化数据库."""
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=get_engine())
    logger.info("Database initialized successfully")


def get_db_session() -> Generator[Session, None, None]:
    """获取数据库会话."""
    session = get_session_local()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
