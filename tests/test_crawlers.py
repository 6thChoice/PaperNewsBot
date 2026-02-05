"""爬虫模块测试."""

import pytest
from datetime import datetime, timedelta

from src.crawlers import ArxivCrawler, OpenReviewCrawler, PaperMetadata


class TestArxivCrawler:
    """测试 arXiv 爬虫."""

    def test_init(self):
        """测试初始化."""
        crawler = ArxivCrawler(max_results=10)
        assert crawler.max_results == 10
        assert crawler.source_name == "arxiv"

    def test_build_search_query_with_categories(self):
        """测试构建分类查询."""
        crawler = ArxivCrawler()
        query = crawler._build_search_query(categories=["cs.AI", "cs.CL"])
        assert "cat:cs.AI" in query
        assert "cat:cs.CL" in query
        assert "OR" in query

    def test_build_search_query_with_query(self):
        """测试构建关键词查询."""
        crawler = ArxivCrawler()
        query = crawler._build_search_query(query="machine learning")
        assert "machine learning" in query

    def test_build_search_query_combined(self):
        """测试构建组合查询."""
        crawler = ArxivCrawler()
        query = crawler._build_search_query(
            categories=["cs.AI"],
            query="machine learning"
        )
        assert "cat:cs.AI" in query
        assert "machine learning" in query
        assert "AND" in query


class TestOpenReviewCrawler:
    """测试 OpenReview 爬虫."""

    def test_init(self):
        """测试初始化."""
        crawler = OpenReviewCrawler(max_results=10)
        assert crawler.max_results == 10
        assert crawler.source_name == "openreview"

    def test_get_invitation_ids(self):
        """测试获取邀请 ID."""
        crawler = OpenReviewCrawler()
        venues = ["ICLR", "NeurIPS"]
        invitation_ids = crawler._get_invitation_ids(venues)

        assert len(invitation_ids) > 0
        assert any("ICLR" in id for id in invitation_ids)
        assert any("NeurIPS" in id for id in invitation_ids)


class TestPaperMetadata:
    """测试论文元数据."""

    def test_to_dict(self):
        """测试转换为字典."""
        metadata = PaperMetadata(
            external_id="1234.5678",
            source="arxiv",
            title="Test Paper",
            authors=["Author 1", "Author 2"],
            abstract="This is a test abstract.",
            publish_date=datetime(2024, 1, 1),
            venue="arXiv",
            source_url="https://arxiv.org/abs/1234.5678",
        )

        data = metadata.to_dict()
        assert data["external_id"] == "1234.5678"
        assert data["title"] == "Test Paper"
        assert data["authors"] == "Author 1, Author 2"
        assert data["publish_date"] == "2024-01-01T00:00:00"
