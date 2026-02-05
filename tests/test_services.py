"""服务模块测试."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.services.ai_service import AIService
from src.config import get_settings


class TestAIService:
    """测试 AI 服务."""

    def test_init(self):
        """测试初始化."""
        service = AIService()
        assert service.settings is not None

    def test_build_briefing_prompt(self):
        """测试构建提示词."""
        service = AIService()
        prompt = service._build_briefing_prompt(
            title="Test Paper",
            authors="Author 1, Author 2",
            abstract="This is a test abstract.",
            venue="ICML 2024",
        )

        assert "Test Paper" in prompt
        assert "Author 1, Author 2" in prompt
        assert "This is a test abstract." in prompt
        assert "ICML 2024" in prompt
        assert "核心贡献" in prompt

    def test_build_briefing_prompt_without_venue(self):
        """测试构建无会议信息的提示词."""
        service = AIService()
        prompt = service._build_briefing_prompt(
            title="Test Paper",
            authors="Author 1",
            abstract="Abstract text.",
        )

        assert "Test Paper" in prompt
        assert "发表会议/期刊" not in prompt

    def test_fallback_summary(self):
        """测试备用摘要."""
        service = AIService()
        summary = service._fallback_summary(
            title="Test Paper",
            abstract="A" * 1000,
        )

        assert "Test Paper" in summary
        assert "A" * 500 in summary
        assert "..." in summary
        assert "AI 服务暂时不可用" in summary

    def test_check_interest_with_matches(self):
        """测试兴趣匹配 - 有匹配."""
        service = AIService()
        is_interested, score = service.check_interest(
            title="Machine Learning for NLP",
            abstract="This paper discusses deep learning.",
            keywords=["AI", "ML"],
            user_interests=["machine learning", "nlp"],
        )

        assert is_interested is True
        assert score > 0

    def test_check_interest_no_matches(self):
        """测试兴趣匹配 - 无匹配."""
        service = AIService()
        is_interested, score = service.check_interest(
            title="Quantum Physics",
            abstract="This paper discusses quantum mechanics.",
            keywords=["physics"],
            user_interests=["machine learning", "nlp"],
        )

        assert is_interested is False
        assert score == 0

    def test_check_interest_empty_interests(self):
        """测试兴趣匹配 - 空兴趣列表."""
        service = AIService()
        is_interested, score = service.check_interest(
            title="Any Paper",
            abstract="Any abstract.",
            keywords=[],
            user_interests=[],
        )

        assert is_interested is True
        assert score == 1.0
