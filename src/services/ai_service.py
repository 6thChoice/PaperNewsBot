"""AI 服务模块."""

from typing import List, Optional

from loguru import logger

from src.config import get_settings


class AIService:
    """AI 服务类，用于生成论文简报."""

    def __init__(self):
        """初始化 AI 服务."""
        self.settings = get_settings()
        self._openai_client = None
        self._anthropic_client = None

    @property
    def openai_client(self):
        """获取 OpenAI 客户端."""
        if self._openai_client is None and self.settings.openai_api_key:
            import openai
            client_kwargs = {"api_key": self.settings.openai_api_key}
            # 如果配置了自定义 base_url，则使用
            if self.settings.openai_base_url:
                client_kwargs["base_url"] = self.settings.openai_base_url
                logger.info(f"Using custom OpenAI base URL: {self.settings.openai_base_url}")
            self._openai_client = openai.OpenAI(**client_kwargs)
        return self._openai_client

    @property
    def anthropic_client(self):
        """获取 Anthropic 客户端."""
        if self._anthropic_client is None and self.settings.anthropic_api_key:
            import anthropic
            client_kwargs = {"api_key": self.settings.anthropic_api_key}
            # 如果配置了自定义 base_url，则使用
            if self.settings.anthropic_base_url:
                client_kwargs["base_url"] = self.settings.anthropic_base_url
                logger.info(f"Using custom Anthropic base URL: {self.settings.anthropic_base_url}")
            self._anthropic_client = anthropic.Anthropic(**client_kwargs)
        return self._anthropic_client

    def generate_briefing(
        self,
        title: str,
        authors: str,
        abstract: str,
        venue: Optional[str] = None,
    ) -> str:
        """生成论文简报."""
        prompt = self._build_briefing_prompt(title, authors, abstract, venue)

        if self.openai_client:
            return self._generate_with_openai(prompt)
        elif self.anthropic_client:
            return self._generate_with_anthropic(prompt)
        else:
            logger.warning("No AI API key configured, using fallback summary")
            return self._fallback_summary(title, abstract)

    def _build_briefing_prompt(
        self,
        title: str,
        authors: str,
        abstract: str,
        venue: Optional[str] = None,
    ) -> str:
        """构建简报生成提示词."""
        venue_info = f"发表会议/期刊: {venue}\n" if venue else ""

        return f"""请为以下学术论文生成一份简洁的简报（用中文）：

论文标题: {title}
作者: {authors}
{venue_info}摘要:
{abstract}

请按照以下格式生成简报：

📄 **{title}**

👥 **作者**: {authors}

🎯 **核心贡献**:
- [简要概括论文的主要贡献，2-3点]

🔍 **方法概述**:
[简要描述论文使用的方法，1-2句话]

📊 **主要结果**:
[如果有实验结果，简要概括]

💡 **关键见解**:
[论文的核心观点或创新点]

请确保简报简洁明了，突出论文的核心价值。"""

    def _generate_with_openai(self, prompt: str) -> str:
        """使用 OpenAI 生成简报."""
        try:
            response = self.openai_client.chat.completions.create(
                model=self.settings.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位专业的学术论文分析助手，擅长提炼论文的核心观点并生成简洁的简报。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self._fallback_summary(prompt, "")

    def _generate_with_anthropic(self, prompt: str) -> str:
        """使用 Anthropic 生成简报."""
        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=800,
                temperature=0.7,
                system="你是一位专业的学术论文分析助手，擅长提炼论文的核心观点并生成简洁的简报。",
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return self._fallback_summary(prompt, "")

    def _fallback_summary(self, title: str, abstract: str) -> str:
        """生成备用摘要."""
        return f"""📄 **{title}**

📝 **摘要**:
{abstract[:500]}{"..." if len(abstract) > 500 else ""}

⚠️ *注：AI 服务暂时不可用，以上为原始摘要。"""

    def check_interest(
        self,
        title: str,
        abstract: str,
        keywords: List[str],
        user_interests: List[str],
    ) -> tuple[bool, float]:
        """检查论文是否符合用户兴趣."""
        if not user_interests:
            return True, 1.0

        text = f"{title} {abstract} {' '.join(keywords)}".lower()
        match_count = 0

        for interest in user_interests:
            interest_lower = interest.lower()
            if interest_lower in text:
                match_count += 1

        score = match_count / len(user_interests) if user_interests else 0
        is_interested = score >= 0.3 or match_count > 0

        return is_interested, score
