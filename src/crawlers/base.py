"""爬虫基类定义."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Iterator


@dataclass
class PaperMetadata:
    """论文元数据."""

    external_id: str
    source: str
    title: str
    authors: List[str]
    abstract: str
    publish_date: Optional[datetime] = None
    venue: Optional[str] = None
    pdf_url: Optional[str] = None
    source_url: str = ""
    keywords: List[str] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        """转换为字典."""
        return {
            "external_id": self.external_id,
            "source": self.source,
            "title": self.title,
            "authors": ", ".join(self.authors) if isinstance(self.authors, list) else self.authors,
            "abstract": self.abstract,
            "publish_date": self.publish_date.isoformat() if self.publish_date else None,
            "venue": self.venue,
            "pdf_url": self.pdf_url,
            "source_url": self.source_url,
            "keywords": ", ".join(self.keywords) if self.keywords else None,
        }


class BaseCrawler(ABC):
    """爬虫基类."""

    def __init__(self, max_results: int = 50):
        """初始化爬虫.

        Args:
            max_results: 每次获取的最大结果数
        """
        self.max_results = max_results

    @property
    @abstractmethod
    def source_name(self) -> str:
        """返回数据源名称."""
        pass

    @abstractmethod
    def fetch_papers(
        self,
        categories: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        query: Optional[str] = None,
    ) -> Iterator[PaperMetadata]:
        """获取论文列表.

        Args:
            categories: 论文分类列表
            since: 起始日期
            query: 搜索查询

        Yields:
            PaperMetadata: 论文元数据
        """
        pass

    def search_by_keywords(
        self,
        keywords: List[str],
        max_results: Optional[int] = None,
    ) -> Iterator[PaperMetadata]:
        """根据关键词搜索论文.

        Args:
            keywords: 关键词列表
            max_results: 最大结果数

        Yields:
            PaperMetadata: 论文元数据
        """
        query = " OR ".join(keywords)
        yield from self.fetch_papers(query=query, max_results=max_results or self.max_results)
