"""OpenReview 论文爬虫."""

from datetime import datetime, timedelta
from typing import Iterator, List, Optional

import openreview
from loguru import logger

from src.crawlers.base import BaseCrawler, PaperMetadata


class OpenReviewCrawler(BaseCrawler):
    """OpenReview 论文爬虫."""

    def __init__(self, max_results: int = 50):
        """初始化 OpenReview 爬虫.

        Args:
            max_results: 每次获取的最大结果数
        """
        super().__init__(max_results)
        self.client = openreview.Client(baseurl="https://api.openreview.net")

    @property
    def source_name(self) -> str:
        """返回数据源名称."""
        return "openreview"

    def fetch_papers(
        self,
        venues: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[PaperMetadata]:
        """获取 OpenReview 论文列表.

        Args:
            venues: 会议列表，如 ["ICLR", "NeurIPS"]
            since: 起始日期
            query: 搜索查询
            max_results: 最大结果数

        Yields:
            PaperMetadata: 论文元数据
        """
        max_results = max_results or self.max_results
        venues = venues or ["ICLR", "NeurIPS", "ICML"]

        logger.info(f"Fetching papers from OpenReview for venues: {venues}")

        try:
            # 获取所有活跃的会议邀请
            invitation_ids = self._get_invitation_ids(venues)

            for invitation_id in invitation_ids:
                logger.debug(f"Fetching submissions for invitation: {invitation_id}")

                # 获取提交记录
                submissions = self.client.get_all_notes(
                    invitation=invitation_id,
                    details="directReplies",
                )

                count = 0
                for submission in submissions:
                    if count >= max_results:
                        break

                    # 过滤日期
                    if since:
                        cdate = datetime.fromtimestamp(submission.cdate / 1000) if submission.cdate else None
                        if cdate and cdate < since:
                            continue

                    paper = self._convert_to_metadata(submission, invitation_id)
                    if paper:
                        logger.debug(f"Fetched paper: {paper.title[:50]}...")
                        yield paper
                        count += 1

        except Exception as e:
            logger.error(f"Error fetching papers from OpenReview: {e}")
            raise

    def _get_invitation_ids(self, venues: List[str]) -> List[str]:
        """获取会议邀请 ID 列表.

        Args:
            venues: 会议名称列表

        Returns:
            List[str]: 邀请 ID 列表
        """
        invitation_ids = []

        # 获取当前年份和前几年
        current_year = datetime.utcnow().year
        years = [current_year, current_year - 1]

        for venue in venues:
            for year in years:
                # 构建常见的邀请 ID 模式
                patterns = [
                    f"{venue}.cc/{year}/Conference/-/Blind_Submission",
                    f"{venue}.cc/{year}/Workshop/-/Blind_Submission",
                ]
                invitation_ids.extend(patterns)

        return invitation_ids

    def _convert_to_metadata(
        self,
        submission,
        invitation_id: str,
    ) -> Optional[PaperMetadata]:
        """将 OpenReview 提交转换为论文元数据.

        Args:
            submission: OpenReview 提交记录
            invitation_id: 邀请 ID

        Returns:
            Optional[PaperMetadata]: 论文元数据，如果无法转换则返回 None
        """
        try:
            content = submission.content

            # 提取标题
            title = content.get("title", "")
            if isinstance(title, dict):
                title = title.get("value", "")

            # 提取摘要
            abstract = content.get("abstract", "")
            if isinstance(abstract, dict):
                abstract = abstract.get("value", "")

            if not title or not abstract:
                return None

            # 提取作者
            authors = content.get("authors", [])
            if isinstance(authors, dict):
                authors = authors.get("value", [])
            if not isinstance(authors, list):
                authors = [authors]

            # 提取关键词
            keywords = content.get("keywords", [])
            if isinstance(keywords, dict):
                keywords = keywords.get("value", [])
            if not isinstance(keywords, list):
                keywords = [keywords]

            # 提取日期
            cdate = datetime.fromtimestamp(submission.cdate / 1000) if submission.cdate else None

            # 提取 venue
            venue_parts = invitation_id.split("/")
            venue = f"{venue_parts[0].replace('.cc', '')} {venue_parts[1]}" if len(venue_parts) >= 2 else "OpenReview"

            return PaperMetadata(
                external_id=submission.id,
                source=self.source_name,
                title=title,
                authors=authors,
                abstract=abstract,
                publish_date=cdate,
                venue=venue,
                pdf_url=f"https://openreview.net/pdf?id={submission.id}",
                source_url=f"https://openreview.net/forum?id={submission.id}",
                keywords=keywords,
                raw_data={
                    "invitation": invitation_id,
                    "forum": submission.forum,
                },
            )

        except Exception as e:
            logger.warning(f"Error converting submission {submission.id}: {e}")
            return None

    def get_daily_papers(
        self,
        venues: Optional[List[str]] = None,
        days: int = 1,
    ) -> Iterator[PaperMetadata]:
        """获取指定天数的论文.

        Args:
            venues: 会议列表
            days: 天数

        Yields:
            PaperMetadata: 论文元数据
        """
        since = datetime.utcnow() - timedelta(days=days)
        yield from self.fetch_papers(venues=venues, since=since)
