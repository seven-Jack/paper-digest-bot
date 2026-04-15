#!/usr/bin/env python3
"""Live smoke test for paper retrieval, content extraction, and AI analysis."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from main import analyze_papers, fetch_papers
from src.config_loader import load_config


class StubAnalyzer:
    """Local fallback analyzer for smoke testing without real API keys."""

    def analyze(self, paper: dict, language: str = "en") -> str:
        return json.dumps(
            {
                "title": paper.get("title", "")[:80],
                "content_source": paper.get("content_source", "missing"),
                "content_len": len(paper.get("content", "")),
            },
            ensure_ascii=False,
        )


def build_smoke_config() -> dict:
    """Build a small deterministic config for live smoke tests."""
    config = load_config("config.yaml")
    config["fetch"] = {"days_back": 7, "max_results_per_source": 5}
    config["email"] = {"language": "en", "max_papers": 2}
    config["content_extraction"] = {
        "enabled": True,
        "max_chars": 1200,
        "max_pdf_pages": 2,
        "timeout_seconds": 30,
    }
    config["sources"] = {
        "arxiv": {"enabled": True, "categories": ["physics.atom-ph"]},
        "aps": {"enabled": False, "journals": []},
        "nature": {"enabled": False, "journals": []},
        "science": {"enabled": False, "journals": []},
        "semantic_scholar": {"enabled": False},
        "openalex": {"enabled": False},
        "crossref": {"enabled": False},
        "pubmed": {"enabled": False},
        "biorxiv": {"enabled": False},
    }
    return config


def validate_results(papers: list[dict], expect_real_ai: bool):
    """Validate that papers were parsed and optionally analyzed by a real model."""
    if not papers:
        raise RuntimeError("Smoke test fetched zero papers.")

    parsed = [
        p
        for p in papers
        if p.get("content_source") in {"pdf", "html"} and len(p.get("content", "")) >= 200
    ]
    if not parsed:
        raise RuntimeError("Smoke test fetched papers, but none were parsed into readable content.")

    if expect_real_ai:
        ai_ok = [
            p
            for p in papers
            if p.get("ai_summary")
            and p.get("ai_summary") not in {
                "(Analysis failed)",
                "（分析失败）",
                "(AI analysis not configured)",
                "（AI 分析未配置）",
            }
        ]
        if not ai_ok:
            raise RuntimeError("Smoke test parsed paper content, but AI analysis did not succeed.")


def main():
    config = build_smoke_config()
    papers = fetch_papers(config)[:2]
    use_stub = os.environ.get("SMOKE_TEST_USE_STUB", "").lower() in {"1", "true", "yes"}

    if use_stub:
        with patch("main.get_analyzer", return_value=StubAnalyzer()):
            papers = analyze_papers(papers, config)
    else:
        papers = analyze_papers(papers, config)

    validate_results(papers, expect_real_ai=not use_stub)

    summary = {
        "fetched": len(papers),
        "use_stub": use_stub,
        "samples": [
            {
                "id": p.get("id"),
                "title": p.get("title"),
                "content_source": p.get("content_source", "missing"),
                "content_len": len(p.get("content", "")),
                "ai_summary": p.get("ai_summary", "")[:200],
            }
            for p in papers
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
