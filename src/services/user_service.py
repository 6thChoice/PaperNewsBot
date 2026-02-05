"""用户服务模块."""

from datetime import datetime
from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from src.models.database import User, ResearchField, UserBriefing, get_db_session
from src.config import get_settings


# 预定义的研究领域
DEFAULT_RESEARCH_FIELDS = [
    {
        "name": "machine_learning",
        "name_cn": "机器学习",
        "description": "Machine Learning, Deep Learning, Neural Networks",
        "arxiv_categories": "cs.LG,cs.AI,stat.ML",
        "keywords": "machine learning,deep learning,neural networks,optimization",
    },
    {
        "name": "nlp",
        "name_cn": "自然语言处理",
        "description": "Natural Language Processing, Computational Linguistics",
        "arxiv_categories": "cs.CL,cs.LG",
        "keywords": "natural language processing,LLM,transformer,language model",
    },
    {
        "name": "computer_vision",
        "name_cn": "计算机视觉",
        "description": "Computer Vision, Image Processing, Pattern Recognition",
        "arxiv_categories": "cs.CV",
        "keywords": "computer vision,image recognition,object detection,segmentation",
    },
    {
        "name": "robotics",
        "name_cn": "机器人学",
        "description": "Robotics, Autonomous Systems, Control",
        "arxiv_categories": "cs.RO",
        "keywords": "robotics,autonomous,control,navigation",
    },
    {
        "name": "reinforcement_learning",
        "name_cn": "强化学习",
        "description": "Reinforcement Learning, Multi-agent Systems",
        "arxiv_categories": "cs.LG,cs.AI,cs.MA",
        "keywords": "reinforcement learning,RL,multi-agent,game theory",
    },
    {
        "name": "ai_safety",
        "name_cn": "AI安全与对齐",
        "description": "AI Safety, Alignment, Interpretability",
        "arxiv_categories": "cs.AI,cs.LG,cs.CY",
        "keywords": "AI safety,alignment,interpretability,robustness",
    },
]


class UserService:
    """用户服务类."""

    def __init__(self, db: Optional[Session] = None):
        """初始化用户服务."""
        self.db = db
        self.settings = get_settings()

    def _get_db(self) -> Session:
        """获取数据库会话."""
        if self.db is not None:
            return self.db
        session_gen = get_db_session()
        return next(session_gen)

    def init_research_fields(self) -> None:
        """初始化研究领域数据."""
        db = self._get_db()
        try:
            for field_data in DEFAULT_RESEARCH_FIELDS:
                existing = db.query(ResearchField).filter(
                    ResearchField.name == field_data["name"]
                ).first()
                
                if not existing:
                    field = ResearchField(**field_data)
                    db.add(field)
                    logger.info(f"Created research field: {field_data['name']}")
            
            db.commit()
            logger.info("Research fields initialized successfully")
        except Exception as e:
            db.rollback()
            logger.error(f"Error initializing research fields: {e}")
            raise

    def get_or_create_user(
        self,
        telegram_id: str,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        """获取或创建用户."""
        db = self._get_db()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
            if user:
                # 更新用户信息
                user.username = username or user.username
                user.first_name = first_name or user.first_name
                user.last_name = last_name or user.last_name
                user.last_active_at = datetime.utcnow()
                db.commit()
                logger.info(f"Updated user: {telegram_id}")
            else:
                # 创建新用户
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    daily_paper_limit=10,
                    is_active=True,
                    onboarding_completed=False,
                    crawl_history_days=7,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Created new user: {telegram_id}")
            
            return user
        except Exception as e:
            db.rollback()
            logger.error(f"Error getting or creating user: {e}")
            raise

    def get_user_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        """通过 Telegram ID 获取用户."""
        db = self._get_db()
        return db.query(User).options(
            joinedload(User.research_fields)
        ).filter(User.telegram_id == telegram_id).first()

    def get_all_active_users(self) -> List[User]:
        """获取所有活跃用户."""
        db = self._get_db()
        return db.query(User).options(
            joinedload(User.research_fields)
        ).filter(User.is_active == True).all()

    def set_user_research_fields(
        self,
        telegram_id: str,
        field_ids: List[int],
    ) -> bool:
        """设置用户的研究领域."""
        db = self._get_db()
        try:
            # 直接查询用户，不通过 get_user_by_telegram_id 避免会话问题
            from sqlalchemy.orm import joinedload
            user = db.query(User).options(
                joinedload(User.research_fields)
            ).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                logger.error(f"User not found: {telegram_id}")
                return False

            # 清除现有领域
            user.research_fields.clear()
            
            # 添加新领域
            for field_id in field_ids:
                field = db.query(ResearchField).filter(ResearchField.id == field_id).first()
                if field:
                    user.research_fields.append(field)
            
            user.onboarding_completed = True
            db.commit()
            logger.info(f"Set research fields for user {telegram_id}: {field_ids}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error setting research fields: {e}")
            return False

    def update_user_settings(
        self,
        telegram_id: str,
        daily_paper_limit: Optional[int] = None,
        is_active: Optional[bool] = None,
        crawl_history_days: Optional[int] = None,
    ) -> bool:
        """更新用户设置."""
        db = self._get_db()
        try:
            # 直接查询用户，避免会话问题
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return False

            if daily_paper_limit is not None:
                user.daily_paper_limit = max(1, min(50, daily_paper_limit))
            
            if is_active is not None:
                user.is_active = is_active
            
            if crawl_history_days is not None:
                user.crawl_history_days = max(1, min(30, crawl_history_days))
            
            db.commit()
            logger.info(f"Updated settings for user {telegram_id}: limit={daily_paper_limit}, days={crawl_history_days}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating user settings: {e}")
            return False

    def get_research_fields(self) -> List[ResearchField]:
        """获取所有研究领域."""
        db = self._get_db()
        return db.query(ResearchField).filter(ResearchField.is_active == True).all()

    def get_user_pending_briefings(
        self,
        telegram_id: str,
        limit: Optional[int] = None,
    ) -> List[UserBriefing]:
        """获取用户的待发送简报."""
        db = self._get_db()
        user = self.get_user_by_telegram_id(telegram_id)
        
        if not user:
            return []
        
        query = db.query(UserBriefing).options(
            joinedload(UserBriefing.briefing).joinedload(UserBriefing.briefing.property.mapper.class_.paper)
        ).filter(
            UserBriefing.user_id == user.id,
            UserBriefing.is_sent == False,
        ).order_by(UserBriefing.created_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()

    def get_user_sent_briefings(
        self,
        telegram_id: str,
        limit: int = 10,
    ) -> List[UserBriefing]:
        """获取用户已发送的简报（历史记录）."""
        db = self._get_db()
        user = self.get_user_by_telegram_id(telegram_id)
        
        if not user:
            return []
        
        return db.query(UserBriefing).options(
            joinedload(UserBriefing.briefing).joinedload(UserBriefing.briefing.property.mapper.class_.paper)
        ).filter(
            UserBriefing.user_id == user.id,
            UserBriefing.is_sent == True,
        ).order_by(UserBriefing.sent_at.desc()).limit(limit).all()

    def mark_briefing_sent(self, user_briefing_id: int) -> bool:
        """标记简报为已发送."""
        db = self._get_db()
        try:
            user_briefing = db.query(UserBriefing).filter(
                UserBriefing.id == user_briefing_id
            ).first()
            
            if user_briefing:
                user_briefing.is_sent = True
                user_briefing.sent_at = datetime.utcnow()
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking briefing as sent: {e}")
            return False

    def mark_briefing_read(self, user_briefing_id: int) -> bool:
        """标记简报为已读."""
        db = self._get_db()
        try:
            user_briefing = db.query(UserBriefing).filter(
                UserBriefing.id == user_briefing_id
            ).first()
            
            if user_briefing:
                user_briefing.is_read = True
                user_briefing.read_at = datetime.utcnow()
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking briefing as read: {e}")
            return False

    def mark_briefing_interested(self, user_briefing_id: int) -> bool:
        """标记简报为感兴趣."""
        db = self._get_db()
        try:
            user_briefing = db.query(UserBriefing).filter(
                UserBriefing.id == user_briefing_id
            ).first()
            
            if user_briefing:
                user_briefing.is_interested = True
                db.commit()
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking briefing as interested: {e}")
            return False
