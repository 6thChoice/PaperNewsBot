"""arXiv 论文爬虫."""

from datetime import datetime, timedelta
from typing import Iterator, List, Optional

import arxiv
from loguru import logger

from src.crawlers.base import BaseCrawler, PaperMetadata


class ArxivCrawler(BaseCrawler):
    """arXiv 论文爬虫."""

    def __init__(self, max_results: int = 50):
        """初始化 arXiv 爬虫.

        Args:
            max_results: 每次获取的最大结果数
        """
        super().__init__(max_results)
        self.client = arxiv.Client()

    @property
    def source_name(self) -> str:
        """返回数据源名称."""
        return "arxiv"

    def fetch_papers(
        self,
        categories: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        query: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[PaperMetadata]:
        """获取 arXiv 论文列表.

        Args:
            categories: 论文分类列表，如 ["cs.AI", "cs.CL"]
            since: 起始日期
            query: 搜索查询
            max_results: 最大结果数

        Yields:
            PaperMetadata: 论文元数据
        """
        max_results = max_results or self.max_results

        # 构建搜索查询
        search_query = self._build_search_query(categories, query)

        logger.info(f"Fetching papers from arXiv with query: {search_query}")

        try:
            search = arxiv.Search(
                query=search_query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending,
            )

            count = 0
            filtered_count = 0
            for result in self.client.results(search):
                count += 1
                # 如果指定了起始日期，过滤论文
                if since and result.published.replace(tzinfo=None) < since:
                    filtered_count += 1
                    logger.debug(f"Filtered paper (too old): {result.title[:50]}... published: {result.published}")
                    continue

                paper = self._convert_to_metadata(result)
                logger.debug(f"Fetched paper: {paper.title[:50]}...")
                yield paper

            logger.info(f"arXiv search returned {count} results, filtered {filtered_count} by date (since: {since})")

        except Exception as e:
            logger.error(f"Error fetching papers from arXiv: {e}")
            raise

    def _build_search_query(
        self,
        categories: Optional[List[str]] = None,
        query: Optional[str] = None,
    ) -> str:
        """构建搜索查询.

        Args:
            categories: 论文分类列表
            query: 搜索查询

        Returns:
            str: 搜索查询字符串
        """
        parts = []

        if categories:
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            parts.append(f"({cat_query})")

        if query:
            parts.append(f"({query})")

        return " AND ".join(parts) if parts else ""

    def _convert_to_metadata(self, result: arxiv.Result) -> PaperMetadata:
        """将 arXiv 结果转换为论文元数据.

        Args:
            result: arXiv 搜索结果

        Returns:
            PaperMetadata: 论文元数据
        """
        # 提取作者列表
        authors = [str(author) for author in result.authors]

        # 提取分类作为关键词
        keywords = list(result.categories) if result.categories else []

        return PaperMetadata(
            external_id=result.entry_id.split("/")[-1],
            source=self.source_name,
            title=result.title,
            authors=authors,
            abstract=result.summary,
            publish_date=result.published.replace(tzinfo=None) if result.published else None,
            venue="arXiv",
            pdf_url=result.pdf_url,
            source_url=result.entry_id,
            keywords=keywords,
            raw_data={
                "primary_category": result.primary_category,
                "comment": result.comment,
                "journal_ref": result.journal_ref,
                "doi": result.doi,
            },
        )

    def get_daily_papers(
        self,
        categories: Optional[List[str]] = None,
        days: int = 1,
    ) -> Iterator[PaperMetadata]:
        """获取指定天数的论文.

        Args:
            categories: 论文分类列表
            days: 天数

        Yields:
            PaperMetadata: 论文元数据
        """
        since = datetime.utcnow() - timedelta(days=days)
        yield from self.fetch_papers(categories=categories, since=since)
