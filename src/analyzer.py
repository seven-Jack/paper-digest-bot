"""
AI Analyzer - Multi-provider paper analysis.

Supports: Gemini (Google), OpenAI, Claude (Anthropic).
User selects provider in config; API key comes from environment.
"""

import json
import logging
import os
import urllib.request
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AnalyzerBase(ABC):
    """Abstract base class for AI analyzers."""

    @abstractmethod
    def analyze(self, paper: dict, language: str = "en") -> str:
        """Analyze a paper and return a summary string."""
        ...

    def _build_prompt(self, paper: dict, language: str) -> str:
        """Build the analysis prompt."""
        title = paper.get("title", "N/A")
        abstract = paper.get("abstract", "N/A")
        keywords = ", ".join(paper.get("matched_keywords", []))

        if language == "zh":
            return (
                f"你是一位原子分子物理领域的学术助手。请用中文简要分析以下论文，包括：\n"
                f"1. 核心研究内容（1-2句话）\n"
                f"2. 主要方法或创新点\n"
                f"3. 与以下关键词的相关性说明：{keywords}\n\n"
                f"标题：{title}\n"
                f"摘要：{abstract}\n\n"
                f"请用3-5句话简洁回答，不要使用markdown格式。"
            )
        else:
            return (
                f"You are an academic assistant in atomic and molecular physics. "
                f"Briefly analyze this paper:\n"
                f"1. Core research content (1-2 sentences)\n"
                f"2. Main methods or innovations\n"
                f"3. Relevance to these keywords: {keywords}\n\n"
                f"Title: {title}\n"
                f"Abstract: {abstract}\n\n"
                f"Reply in 3-5 concise sentences, no markdown."
            )


class GeminiAnalyzer(AnalyzerBase):
    """Google Gemini API analyzer."""

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model = "gemini-2.0-flash"

    def analyze(self, paper: dict, language: str = "en") -> str:
        prompt = self._build_prompt(paper, language)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            f":generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 300, "temperature": 0.3},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        candidates = result.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()

        return "(No response from Gemini)"


class OpenAIAnalyzer(AnalyzerBase):
    """OpenAI API analyzer."""

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.model = "gpt-4o-mini"

    def analyze(self, paper: dict, language: str = "en") -> str:
        prompt = self._build_prompt(paper, language)
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0.3,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()

        return "(No response from OpenAI)"


class ClaudeAnalyzer(AnalyzerBase):
    """Anthropic Claude API analyzer."""

    def __init__(self):
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = "claude-sonnet-4-20250514"

    def analyze(self, paper: dict, language: str = "en") -> str:
        prompt = self._build_prompt(paper, language)
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": self.model,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())

        content = result.get("content", [])
        if content:
            return content[0].get("text", "").strip()

        return "(No response from Claude)"


# === Provider Registry ===

_PROVIDERS = {
    "gemini": GeminiAnalyzer,
    "openai": OpenAIAnalyzer,
    "claude": ClaudeAnalyzer,
}

# Map of provider -> required environment variable
_REQUIRED_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}


def get_analyzer(provider: str) -> AnalyzerBase | None:
    """Get an analyzer instance for the given provider."""
    provider = provider.lower().strip()
    if provider not in _PROVIDERS:
        logger.error(f"Unknown AI provider: {provider}. Available: {list(_PROVIDERS.keys())}")
        return None

    env_key = _REQUIRED_KEYS.get(provider, "")
    if env_key and not os.environ.get(env_key):
        logger.warning(f"API key not set: {env_key}. AI analysis will be skipped.")
        return None

    return _PROVIDERS[provider]()
