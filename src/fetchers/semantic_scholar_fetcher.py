"""
Semantic Scholar Fetcher - Fetch papers from Semantic Scholar API.

Semantic Scholar has 200M+ papers across all disciplines.
Free API with rate limit: 100 requests/5 minutes without API key, 1 request/second with API key.
"""

import json
import logging
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class SemanticScholarFetcher:
    """Fetch papers from Semantic Scholar API."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, fields_of_study: list[str] = None, keywords: list[str] = None):
        """
        Initialize the fetcher.
        
        Args:
            fields_of_study: List of fields like ["Physics", "Computer Science", "Biology"]
            keywords: List of keywords to search for
        """
        self.fields_of_study = fields_of_study or []
        self.keywords = keywords or []
        self.api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

    def fetch(self, days_back: int = 7, max_results: int = 100) -> list[dict]:
        """
        Fetch recent papers from Semantic Scholar.
        
        Args:
            days_back: Number of days to look back
            max_results: Maximum number of papers to fetch per query
            
        Returns:
            List of paper dicts
        """
        papers = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        # Search by keywords
        for keyword in self.keywords:
            try:
                results = self._search_papers(keyword, cutoff_str, max_results)
                papers.extend(results)
                logger.info(f"  SemanticScholar/{keyword}: {len(results)} papers")
            except Exception as e:
                logger.error(f"Failed to fetch Semantic Scholar for '{keyword}': {e}")

        # Search by field of study
        for field in self.fields_of_study:
            try:
                results = self._search_by_field(field, cutoff_str, max_results)
                papers.extend(results)
                logger.info(f"  SemanticScholar/{field}: {len(results)} papers")
            except Exception as e:
                logger.error(f"Failed to fetch Semantic Scholar for field '{field}': {e}")

        # Deduplicate by paper ID
        seen_ids = set()
        unique_papers = []
        for paper in papers:
            if paper["id"] not in seen_ids:
                seen_ids.add(paper["id"])
                unique_papers.append(paper)

        return unique_papers

    def _search_papers(self, query: str, date_from: str, limit: int) -> list[dict]:
        """Search papers by keyword query."""
        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": "paperId,title,abstract,authors,url,publicationDate,externalIds,venue",
            "publicationDateOrYear": f"{date_from}:",
        }
        
        url = f"{self.BASE_URL}/paper/search?{urllib.parse.urlencode(params)}"
        return self._fetch_and_parse(url)

    def _search_by_field(self, field: str, date_from: str, limit: int) -> list[dict]:
        """Search papers by field of study."""
        params = {
            "query": field,
            "limit": min(limit, 100),
            "fields": "paperId,title,abstract,authors,url,publicationDate,externalIds,venue",
            "publicationDateOrYear": f"{date_from}:",
            "fieldsOfStudy": field,
        }
        
        url = f"{self.BASE_URL}/paper/search?{urllib.parse.urlencode(params)}"
        return self._fetch_and_parse(url)

    def _fetch_and_parse(self, url: str) -> list[dict]:
        """Fetch URL and parse results into paper dicts."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        papers = []
        for item in data.get("data", []):
            if not item.get("title") or not item.get("abstract"):
                continue

            # Extract DOI if available
            external_ids = item.get("externalIds", {}) or {}
            doi = external_ids.get("DOI", "")
            arxiv_id = external_ids.get("ArXiv", "")

            # Parse authors
            authors = []
            for author in item.get("authors", []):
                if author.get("name"):
                    authors.append(author["name"])

            paper = {
                "id": f"s2:{item.get('paperId', '')}",
                "title": item.get("title", "").strip(),
                "abstract": item.get("abstract", "").strip(),
                "authors": authors,
                "url": item.get("url", f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}"),
                "published": item.get("publicationDate", ""),
                "source": "Semantic Scholar",
                "doi": doi,
                "arxiv_id": arxiv_id,
                "venue": item.get("venue", ""),
            }
            papers.append(paper)

        return papers
