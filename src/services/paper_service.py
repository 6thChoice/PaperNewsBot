"""论文服务模块."""

from datetime import datetime, timedelta
from typing import List, Optional, Set

from loguru import logger
from sqlalchemy.orm import Session

from src.config import get_settings
from src.crawlers import ArxivCrawler, OpenReviewCrawler, PaperMetadata
from src.models import Paper, ResearchField, get_db_session


class PaperService:
    """论文服务类."""

    def __init__(self, db_session: Optional[Session] = None):
        """初始化论文服务."""
        self.settings = get_settings()
        self.db = db_session
        self._arxiv_crawler = None
        self._openreview_crawler = None

    @property
    def arxiv_crawler(self) -> ArxivCrawler:
        """获取 arXiv 爬虫."""
        if self._arxiv_crawler is None:
            self._arxiv_crawler = ArxivCrawler(max_results=self.settings.arxiv_max_results)
        return self._arxiv_crawler

    @property
    def openreview_crawler(self) -> OpenReviewCrawler:
        """获取 OpenReview 爬虫."""
        if self._openreview_crawler is None:
            self._openreview_crawler = OpenReviewCrawler()
        return self._openreview_crawler

    def _get_db(self) -> Session:
        """获取数据库会话."""
        if self.db is not None:
            return self.db
        session_gen = get_db_session()
        return next(session_gen)

    def fetch_and_save_papers(
        self,
        days: int = 1,
        categories: Optional[List[str]] = None,
        venues: Optional[List[str]] = None,
    ) -> List[Paper]:
        """获取并保存论文."""
        papers = []

        try:
            arxiv_papers = self._fetch_arxiv_papers(days, categories)
            papers.extend(arxiv_papers)
            logger.info(f"Fetched {len(arxiv_papers)} papers from arXiv")
        except Exception as e:
            logger.error(f"Error fetching arXiv papers: {e}")

        try:
            openreview_papers = self._fetch_openreview_papers(days, venues)
            papers.extend(openreview_papers)
            logger.info(f"Fetched {len(openreview_papers)} papers from OpenReview")
        except Exception as e:
            logger.error(f"Error fetching OpenReview papers: {e}")

        return papers

    def fetch_papers_for_user(
        self,
        research_fields: List[ResearchField],
        days: int = 7,
    ) -> List[Paper]:
        """根据用户研究领域获取论文."""
        # 收集所有需要的分类
        all_categories: Set[str] = set()
        for field in research_fields:
            all_categories.update(field.get_arxiv_categories_list())
        
        if not all_categories:
            logger.warning("No research fields configured for user")
            return []
        
        logger.info(f"Fetching papers for categories: {all_categories}, days: {days}")
        
        # 爬取论文
        papers = self.fetch_and_save_papers(
            days=days,
            categories=list(all_categories),
        )
        
        return papers

    def _fetch_arxiv_papers(
        self,
        days: int,
        categories: Optional[List[str]] = None,
    ) -> List[Paper]:
        """获取 arXiv 论文.

        注意: arXiv 论文发布有延迟(美东时间下午发布,对应 UTC 晚上),
        所以 days=1 可能抓不到论文。这里使用 max(days, 2) 确保至少获取2天的论文。
        """
        categories = categories or self.settings.arxiv_categories_list
        # arXiv 论文发布有延迟,确保至少获取2天的论文
        effective_days = max(days, 2)
        since = datetime.utcnow() - timedelta(days=effective_days)

        logger.info(f"Fetching arXiv papers for last {effective_days} days (requested: {days})")

        papers = []
        skipped_count = 0
        for metadata in self.arxiv_crawler.fetch_papers(categories=categories, since=since):
            paper = self._save_paper(metadata)
            if paper:
                papers.append(paper)
            else:
                skipped_count += 1

        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} existing papers from arXiv (already in database)")

        return papers

    def _fetch_openreview_papers(
        self,
        days: int,
        venues: Optional[List[str]] = None,
    ) -> List[Paper]:
        """获取 OpenReview 论文."""
        venues = venues or self.settings.openreview_conferences_list
        since = datetime.utcnow() - timedelta(days=days)

        papers = []
        for metadata in self.openreview_crawler.fetch_papers(venues=venues, since=since):
            paper = self._save_paper(metadata)
            if paper:
                papers.append(paper)

        return papers

    def _save_paper(self, metadata: PaperMetadata) -> Optional[Paper]:
        """保存论文到数据库."""
        db = self._get_db()
        close_session = self.db is None

        try:
            existing = db.query(Paper).filter(
                Paper.external_id == metadata.external_id,
                Paper.source == metadata.source,
            ).first()

            if existing:
                # 使用 debug 级别避免日志过多，统计信息在调用方输出
                logger.debug(f"Paper already exists: {metadata.title[:50]}...")
                return None

            paper = Paper(
                external_id=metadata.external_id,
                source=metadata.source,
                title=metadata.title,
                authors=metadata.authors if isinstance(metadata.authors, str) else ", ".join(metadata.authors),
                abstract=metadata.abstract,
                keywords=", ".join(metadata.keywords) if metadata.keywords else None,
                publish_date=metadata.publish_date,
                venue=metadata.venue,
                pdf_url=metadata.pdf_url,
                source_url=metadata.source_url,
            )

            db.add(paper)
            db.commit()
            db.refresh(paper)

            logger.info(f"Saved new paper: {paper.title[:50]}...")
            return paper

        except Exception as e:
            logger.error(f"Error saving paper: {e}")
            db.rollback()
            return None

        finally:
            if close_session:
                db.close()

    def get_papers_for_briefing(
        self,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
        research_fields: Optional[List[ResearchField]] = None,
    ) -> List[Paper]:
        """获取需要生成简报的论文."""
        db = self._get_db()
        close_session = self.db is None

        try:
            from src.models import Briefing
            
            # 查询还没有简报的论文
            query = db.query(Paper).outerjoin(
                Briefing, Paper.id == Briefing.paper_id
            ).filter(Briefing.id == None)

            if since:
                query = query.filter(Paper.publish_date >= since)
            
            # 如果指定了研究领域，根据关键词筛选
            if research_fields:
                all_keywords = []
                for field in research_fields:
                    all_keywords.extend(field.get_keywords_list())
                
                if all_keywords:
                    # 构建关键词筛选条件
                    keyword_conditions = []
                    for keyword in all_keywords:
                        pattern = f"%{keyword}%"
                        keyword_conditions.append(
                            (Paper.title.ilike(pattern)) |
                            (Paper.abstract.ilike(pattern)) |
                            (Paper.keywords.ilike(pattern))
                        )
                    
                    from sqlalchemy import or_
                    if keyword_conditions:
                        query = query.filter(or_(*keyword_conditions))

            query = query.order_by(Paper.publish_date.desc())

            if limit:
                query = query.limit(limit)

            return query.all()

        finally:
            if close_session:
                db.close()

    def get_papers_by_ids(self, paper_ids: List[int]) -> List[Paper]:
        """通过 ID 列表获取论文."""
        db = self._get_db()
        close_session = self.db is None

        try:
            return db.query(Paper).filter(Paper.id.in_(paper_ids)).all()
        finally:
            if close_session:
                db.close()

    def get_paper_by_id(self, paper_id: int) -> Optional[Paper]:
        """通过 ID 获取论文."""
        db = self._get_db()
        close_session = self.db is None

        try:
            return db.query(Paper).filter(Paper.id == paper_id).first()
        finally:
            if close_session:
                db.close()

    def search_papers(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Paper]:
        """搜索论文."""
        db = self._get_db()
        close_session = self.db is None

        try:
            search_pattern = f"%{query}%"
            papers = db.query(Paper).filter(
                (Paper.title.ilike(search_pattern)) |
                (Paper.abstract.ilike(search_pattern)) |
                (Paper.keywords.ilike(search_pattern))
            ).order_by(Paper.publish_date.desc()).limit(limit).all()

            return papers
        finally:
            if close_session:
                db.close()

    def get_recent_papers(
        self,
        days: int = 7,
        limit: int = 50,
    ) -> List[Paper]:
        """获取最近的论文."""
        db = self._get_db()
        close_session = self.db is None

        try:
            since = datetime.utcnow() - timedelta(days=days)
            return db.query(Paper).filter(
                Paper.publish_date >= since
            ).order_by(Paper.publish_date.desc()).limit(limit).all()
        finally:
            if close_session:
                db.close()
