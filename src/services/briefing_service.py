"""简报服务模块."""

from datetime import datetime, timedelta
from typing import List, Optional

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from src.config import get_settings
from src.models import Briefing, Paper, User, UserBriefing, get_db_session
from src.services.ai_service import AIService


class BriefingService:
    """简报服务类."""

    def __init__(
        self,
        db_session: Optional[Session] = None,
        ai_service: Optional[AIService] = None,
    ):
        """初始化简报服务."""
        self.settings = get_settings()
        self.db = db_session
        self.ai_service = ai_service or AIService()

    def _get_db(self) -> Session:
        """获取数据库会话."""
        if self.db is not None:
            return self.db
        session_gen = get_db_session()
        return next(session_gen)

    def generate_briefings(
        self,
        papers: Optional[List[Paper]] = None,
        max_papers: Optional[int] = None,
        research_fields: Optional[List] = None,
    ) -> List[Briefing]:
        """为论文生成简报."""
        max_papers = max_papers or self.settings.max_papers_per_day

        if papers is None:
            papers = self._get_pending_papers(max_papers, research_fields)

        briefings = []
        for paper in papers:
            briefing = self._generate_single_briefing(paper)
            if briefing:
                briefings.append(briefing)

        logger.info(f"Generated {len(briefings)} briefings")
        return briefings

    def _get_pending_papers(
        self,
        limit: int,
        research_fields: Optional[List] = None,
    ) -> List[Paper]:
        """获取待生成简报的论文."""
        db = self._get_db()
        close_session = self.db is None

        try:
            since = datetime.utcnow() - timedelta(days=7)

            # 查询还没有简报的论文
            query = db.query(Paper).outerjoin(
                Briefing, Paper.id == Briefing.paper_id
            ).filter(
                Briefing.id == None,
                Paper.publish_date >= since,
            )

            # 如果指定了研究领域，根据关键词筛选
            if research_fields:
                all_keywords = []
                for field in research_fields:
                    all_keywords.extend(field.get_keywords_list())

                if all_keywords:
                    from sqlalchemy import or_
                    keyword_conditions = []
                    for keyword in all_keywords:
                        pattern = f"%{keyword}%"
                        keyword_conditions.append(
                            (Paper.title.ilike(pattern)) |
                            (Paper.abstract.ilike(pattern)) |
                            (Paper.keywords.ilike(pattern))
                        )
                    if keyword_conditions:
                        query = query.filter(or_(*keyword_conditions))

            papers = query.order_by(Paper.publish_date.desc()).limit(limit).all()
            return papers

        finally:
            if close_session:
                db.close()

    def _generate_single_briefing(self, paper: Paper) -> Optional[Briefing]:
        """为单篇论文生成简报."""
        db = self._get_db()
        close_session = self.db is None

        try:
            existing = db.query(Briefing).filter(Briefing.paper_id == paper.id).first()
            if existing:
                logger.debug(f"Briefing already exists for paper: {paper.title[:50]}...")
                return existing

            content = self.ai_service.generate_briefing(
                title=paper.title,
                authors=paper.authors,
                abstract=paper.abstract,
                venue=paper.venue,
            )

            ai_model = "openai" if self.settings.openai_api_key else "anthropic" if self.settings.anthropic_api_key else "fallback"
            
            briefing = Briefing(
                paper_id=paper.id,
                content=content,
                ai_model=ai_model,
            )

            db.add(briefing)
            db.commit()
            db.refresh(briefing)

            logger.info(f"Generated briefing for paper: {paper.title[:50]}...")
            return briefing

        except Exception as e:
            logger.error(f"Error generating briefing for paper {paper.id}: {e}")
            db.rollback()
            return None

        finally:
            if close_session:
                db.close()

    def create_user_briefings(self, user: User) -> List[UserBriefing]:
        """为用户创建简报关联（将现有简报分配给用户）."""
        db = self._get_db()
        close_session = self.db is None

        try:
            # 获取用户的研究领域关键词
            all_keywords = []
            for field in user.research_fields:
                all_keywords.extend(field.get_keywords_list())

            # 查询还没有分配给该用户的简报
            from sqlalchemy import select
            existing_briefing_ids = select(UserBriefing.briefing_id).where(
                UserBriefing.user_id == user.id
            )

            query = db.query(Briefing).join(Paper).filter(
                ~Briefing.id.in_(existing_briefing_ids)
            )

            # 根据用户研究领域筛选
            if all_keywords:
                from sqlalchemy import or_
                keyword_conditions = []
                for keyword in all_keywords:
                    pattern = f"%{keyword}%"
                    keyword_conditions.append(
                        (Paper.title.ilike(pattern)) |
                        (Paper.abstract.ilike(pattern)) |
                        (Paper.keywords.ilike(pattern))
                    )
                if keyword_conditions:
                    query = query.filter(or_(*keyword_conditions))

            # 按发布时间排序，最新的在前
            briefings = query.order_by(Paper.publish_date.desc()).limit(user.daily_paper_limit * 3).all()

            user_briefings = []
            for briefing in briefings:
                user_briefing = UserBriefing(
                    user_id=user.id,
                    briefing_id=briefing.id,
                    is_sent=False,
                )
                db.add(user_briefing)
                user_briefings.append(user_briefing)

            db.commit()
            logger.info(f"Created {len(user_briefings)} user briefings for user {user.telegram_id}")
            return user_briefings

        except Exception as e:
            logger.error(f"Error creating user briefings: {e}")
            db.rollback()
            return []

        finally:
            if close_session:
                db.close()

    def get_user_pending_briefings(
        self,
        user: User,
        limit: Optional[int] = None,
    ) -> List[UserBriefing]:
        """获取用户的待发送简报（按时间倒序）."""
        db = self._get_db()
        close_session = self.db is None

        try:
            query = db.query(UserBriefing).options(
                joinedload(UserBriefing.briefing).joinedload(Briefing.paper)
            ).filter(
                UserBriefing.user_id == user.id,
                UserBriefing.is_sent == False,
            ).order_by(UserBriefing.created_at.desc())

            if limit:
                query = query.limit(limit)

            user_briefings = query.all()
            
            # 预加载数据
            if close_session:
                for ub in user_briefings:
                    if ub.briefing and ub.briefing.paper:
                        _ = ub.briefing.paper.title
            
            return user_briefings

        finally:
            if close_session:
                db.close()

    def get_user_sent_briefings(
        self,
        user: User,
        limit: int = 20,
    ) -> List[UserBriefing]:
        """获取用户已发送的简报历史."""
        db = self._get_db()
        close_session = self.db is None

        try:
            query = db.query(UserBriefing).options(
                joinedload(UserBriefing.briefing).joinedload(Briefing.paper)
            ).filter(
                UserBriefing.user_id == user.id,
                UserBriefing.is_sent == True,
            ).order_by(UserBriefing.sent_at.desc())

            user_briefings = query.limit(limit).all()
            
            # 预加载数据
            if close_session:
                for ub in user_briefings:
                    if ub.briefing and ub.briefing.paper:
                        _ = ub.briefing.paper.title
            
            return user_briefings

        finally:
            if close_session:
                db.close()

    def mark_user_briefing_sent(self, user_briefing_id: int) -> bool:
        """标记用户简报为已发送."""
        db = self._get_db()
        close_session = self.db is None

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
            logger.error(f"Error marking user briefing as sent: {e}")
            db.rollback()
            return False

        finally:
            if close_session:
                db.close()

    def mark_user_briefing_read(self, user_briefing_id: int) -> bool:
        """标记用户简报为已读."""
        db = self._get_db()
        close_session = self.db is None

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
            logger.error(f"Error marking user briefing as read: {e}")
            db.rollback()
            return False

        finally:
            if close_session:
                db.close()

    def mark_user_briefing_interested(self, user_briefing_id: int) -> bool:
        """标记用户简报为感兴趣."""
        db = self._get_db()
        close_session = self.db is None

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
            logger.error(f"Error marking user briefing as interested: {e}")
            db.rollback()
            return False

        finally:
            if close_session:
                db.close()

    def format_briefing_for_telegram(self, user_briefing: UserBriefing) -> str:
        """格式化简报为 Telegram 消息."""
        briefing = user_briefing.briefing
        if not briefing:
            return "简报数据缺失"
        
        paper = briefing.paper
        if not paper:
            return briefing.content

        header = f"📚 *每日论文简报*\n\n"
        footer = f"\n\n🔗 [查看原文]({paper.source_url})"
        if paper.pdf_url:
            footer += f" | [PDF]({paper.pdf_url})"

        return header + briefing.content + footer

    # 保留旧方法用于向后兼容
    def get_pending_briefings(self, limit: Optional[int] = None) -> List[Briefing]:
        """获取待发送的简报（旧方法，用于兼容）."""
        db = self._get_db()
        close_session = self.db is None

        try:
            query = db.query(Briefing).order_by(Briefing.created_at.desc())

            if limit:
                query = query.limit(limit)

            return query.all()

        finally:
            if close_session:
                db.close()

    def get_all_briefings(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Briefing]:
        """获取所有简报."""
        db = self._get_db()
        close_session = self.db is None

        try:
            query = db.query(Briefing).options(
                joinedload(Briefing.paper)
            ).order_by(Briefing.created_at.desc()).offset(offset).limit(limit)

            briefings = query.all()
            
            # 预加载数据
            if close_session:
                for briefing in briefings:
                    if briefing.paper:
                        _ = briefing.paper.title
            
            return briefings

        finally:
            if close_session:
                db.close()
