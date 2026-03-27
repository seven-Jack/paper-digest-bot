#!/usr/bin/env python3
"""
Paper Digest Bot - Daily academic paper digest with AI analysis.
Main entry point for the GitHub Actions workflow.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

from src.fetchers.arxiv_fetcher import ArxivFetcher
from src.fetchers.aps_fetcher import APSFetcher
from src.weight_manager import WeightManager
from src.analyzer import get_analyzer
from src.email_builder import EmailBuilder
from src.email_sender import send_email
from src.config_loader import load_config

# Optional fetchers - import with fallback
try:
    from src.fetchers.semantic_scholar_fetcher import SemanticScholarFetcher
except ImportError:
    SemanticScholarFetcher = None

try:
    from src.fetchers.openalex_fetcher import OpenAlexFetcher
except ImportError:
    OpenAlexFetcher = None

try:
    from src.fetchers.crossref_fetcher import CrossRefFetcher
except ImportError:
    CrossRefFetcher = None

try:
    from src.fetchers.pubmed_fetcher import PubMedFetcher
except ImportError:
    PubMedFetcher = None

try:
    from src.fetchers.biorxiv_fetcher import BioRxivFetcher
except ImportError:
    BioRxivFetcher = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def fetch_papers(config: dict) -> list[dict]:
    """Fetch papers from all enabled sources."""
    papers = []
    sources = config.get("sources", {})
    
    # 从配置中读取 days_back，默认为 2 天
    days_back = config.get("fetch", {}).get("days_back", 2)
    max_results = config.get("fetch", {}).get("max_results_per_source", 100)
    logger.info(f"Fetching papers from the last {days_back} days...")

    # arXiv
    if sources.get("arxiv", {}).get("enabled", False):
        logger.info("Fetching from arXiv...")
        fetcher = ArxivFetcher(sources["arxiv"].get("categories", []))
        papers.extend(fetcher.fetch(days_back=days_back))

    # APS (Physical Review journals)
    if sources.get("aps", {}).get("enabled", False):
        logger.info("Fetching from APS journals...")
        fetcher = APSFetcher(sources["aps"].get("journals", []))
        papers.extend(fetcher.fetch(days_back=days_back))

    # Semantic Scholar
    if sources.get("semantic_scholar", {}).get("enabled", False):
        if SemanticScholarFetcher:
            logger.info("Fetching from Semantic Scholar...")
            ss_config = sources["semantic_scholar"]
            fetcher = SemanticScholarFetcher(
                fields_of_study=ss_config.get("fields", []),
                keywords=ss_config.get("keywords", [])
            )
            papers.extend(fetcher.fetch(days_back=days_back, max_results=max_results))
        else:
            logger.warning("Semantic Scholar fetcher not available")

    # OpenAlex
    if sources.get("openalex", {}).get("enabled", False):
        if OpenAlexFetcher:
            logger.info("Fetching from OpenAlex...")
            oa_config = sources["openalex"]
            fetcher = OpenAlexFetcher(
                concepts=oa_config.get("concepts", []),
                keywords=oa_config.get("keywords", [])
            )
            papers.extend(fetcher.fetch(days_back=days_back, max_results=max_results))
        else:
            logger.warning("OpenAlex fetcher not available")

    # CrossRef
    if sources.get("crossref", {}).get("enabled", False):
        if CrossRefFetcher:
            logger.info("Fetching from CrossRef...")
            cr_config = sources["crossref"]
            fetcher = CrossRefFetcher(
                keywords=cr_config.get("keywords", []),
                journals=cr_config.get("journals", [])
            )
            papers.extend(fetcher.fetch(days_back=days_back, max_results=max_results))
        else:
            logger.warning("CrossRef fetcher not available")

    # PubMed
    if sources.get("pubmed", {}).get("enabled", False):
        if PubMedFetcher:
            logger.info("Fetching from PubMed...")
            pm_config = sources["pubmed"]
            fetcher = PubMedFetcher(
                keywords=pm_config.get("keywords", []),
                mesh_terms=pm_config.get("mesh_terms", [])
            )
            papers.extend(fetcher.fetch(days_back=days_back, max_results=max_results))
        else:
            logger.warning("PubMed fetcher not available")

    # bioRxiv / medRxiv
    if sources.get("biorxiv", {}).get("enabled", False):
        if BioRxivFetcher:
            logger.info("Fetching from bioRxiv/medRxiv...")
            bio_config = sources["biorxiv"]
            fetcher = BioRxivFetcher(
                servers=bio_config.get("servers", ["biorxiv", "medrxiv"]),
                subjects=bio_config.get("subjects", [])
            )
            papers.extend(fetcher.fetch(days_back=days_back, max_results=max_results))
        else:
            logger.warning("bioRxiv fetcher not available")

    logger.info(f"Total papers fetched: {len(papers)}")
    return papers


def filter_and_rank(papers: list[dict], weight_manager: WeightManager) -> list[dict]:
    """Filter papers by keyword relevance and rank by weight score."""
    scored = []
    for paper in papers:
        score, matched_keywords = weight_manager.score_paper(paper)
        if score > 0:
            paper["relevance_score"] = score
            paper["matched_keywords"] = matched_keywords
            scored.append(paper)

    scored.sort(key=lambda p: p["relevance_score"], reverse=True)
    logger.info(f"Papers after filtering: {len(scored)}")
    return scored


def deduplicate(papers: list[dict], cache_path: str) -> list[dict]:
    """Remove papers that were already sent in previous digests."""
    if os.path.exists(cache_path):
        with open(cache_path, "r") as f:
            cache = json.load(f)
    else:
        cache = {"sent_ids": []}

    sent_ids = set(cache.get("sent_ids", []))
    new_papers = [p for p in papers if p.get("id") not in sent_ids]

    # Update cache with new paper IDs
    for p in new_papers:
        sent_ids.add(p.get("id", ""))
    # Keep only last 30 days of IDs (approx 600 papers)
    cache["sent_ids"] = list(sent_ids)[-2000:]
    cache["last_updated"] = datetime.now(timezone.utc).isoformat()

    with open(cache_path, "w") as f:
        json.dump(cache, f, indent=2)

    logger.info(f"New papers after dedup: {len(new_papers)}")
    return new_papers


def analyze_papers(papers: list[dict], config: dict) -> list[dict]:
    """Use AI to analyze each paper's abstract."""
    provider = config.get("ai_provider", "gemini")
    language = config.get("email", {}).get("language", "en")

    analyzer = get_analyzer(provider)
    if analyzer is None:
        logger.warning(f"AI provider '{provider}' not configured, skipping analysis.")
        for p in papers:
            p["ai_summary"] = "（AI 分析未配置）" if language == "zh" else "(AI analysis not configured)"
        return papers

    for i, paper in enumerate(papers):
        logger.info(f"Analyzing paper {i+1}/{len(papers)}: {paper.get('title', '')[:60]}...")
        try:
            paper["ai_summary"] = analyzer.analyze(paper, language)
        except Exception as e:
            logger.error(f"Analysis failed for paper {paper.get('id')}: {e}")
            paper["ai_summary"] = "（分析失败）" if language == "zh" else "(Analysis failed)"

    return papers


def main():
    parser = argparse.ArgumentParser(description="Paper Digest Bot")
    parser.add_argument("--dry-run", action="store_true", help="Print email content without sending")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)

    # Initialize weight manager
    keywords_path = os.path.join(data_dir, "keywords.json")
    weight_manager = WeightManager(keywords_path)
    weight_manager.apply_daily_decay(config.get("weights", {}))

    # Fetch → Filter → Deduplicate → Analyze → Email
    papers = fetch_papers(config)
    papers = filter_and_rank(papers, weight_manager)

    max_papers = config.get("email", {}).get("max_papers", 20)
    papers = papers[:max_papers]

    cache_path = os.path.join(data_dir, "paper_cache.json")
    papers = deduplicate(papers, cache_path)

    if not papers:
        logger.info("No new relevant papers found today. Skipping email.")
        return

    papers = analyze_papers(papers, config)

    # Build email
    language = config.get("email", {}).get("language", "en")
    repo_owner = os.environ.get("GITHUB_REPOSITORY_OWNER", "")
    repo_name = os.environ.get("GITHUB_REPOSITORY", "").split("/")[-1] if os.environ.get("GITHUB_REPOSITORY") else ""

    builder = EmailBuilder(language=language, repo_owner=repo_owner, repo_name=repo_name)
    subject, html_body = builder.build(papers)

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"Subject: {subject}")
        print(f"{'='*60}")
        print(f"Papers: {len(papers)}")
        for p in papers:
            print(f"  [{p.get('relevance_score', 0):.1f}] {p.get('title', 'N/A')[:80]}")
        print(f"{'='*60}")
        # Save HTML for preview
        preview_path = os.path.join(data_dir, "preview.html")
        with open(preview_path, "w", encoding="utf-8") as f:
            f.write(html_body)
        logger.info(f"Email preview saved to {preview_path}")
    else:
        recipient = os.environ.get("EMAIL_ADDRESS", "")
        if not recipient:
            logger.error("EMAIL_ADDRESS not set. Cannot send email.")
            sys.exit(1)
        send_email(subject, html_body, recipient)
        logger.info(f"Digest email sent to {recipient}")


if __name__ == "__main__":
    main()
