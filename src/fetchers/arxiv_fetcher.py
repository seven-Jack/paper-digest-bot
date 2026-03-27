"""Fetch recent papers from arXiv API."""

import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"


class ArxivFetcher:
    """Fetch papers from arXiv for given categories."""

    def __init__(self, categories: list[str]):
        self.categories = categories or ["physics.atom-ph"]

    def fetch(self, days_back: int = 2) -> list[dict]:
        """Fetch recent papers from arXiv."""
        papers = []
        for cat in self.categories:
            try:
                papers.extend(self._fetch_category(cat, days_back))
            except Exception as e:
                logger.error(f"Failed to fetch arXiv category {cat}: {e}")
        return papers

    def _fetch_category(self, category: str, days_back: int) -> list[dict]:
        """Fetch papers from a single arXiv category."""
        query = f"cat:{category}"
        params = (
            f"?search_query={query}"
            f"&sortBy=submittedDate"
            f"&sortOrder=descending"
            f"&max_results=50"
        )
        url = ARXIV_API + params

        logger.info(f"Fetching arXiv: {category}")
        req = urllib.request.Request(url, headers={"User-Agent": "PaperDigestBot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()

        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        papers = []

        for entry in root.findall("atom:entry", ns):
            published_str = entry.findtext("atom:published", "", ns)
            if published_str:
                published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                if published < cutoff:
                    continue

            paper = {
                "id": entry.findtext("atom:id", "", ns).split("/abs/")[-1],
                "title": self._clean_text(entry.findtext("atom:title", "", ns)),
                "abstract": self._clean_text(entry.findtext("atom:summary", "", ns)),
                "authors": [
                    a.findtext("atom:name", "", ns)
                    for a in entry.findall("atom:author", ns)
                ],
                "url": entry.findtext("atom:id", "", ns),
                "published": published_str,
                "source": "arxiv",
                "category": category,
                "doi": "",
            }

            # Try to get DOI
            doi_elem = entry.find("arxiv:doi", ns)
            if doi_elem is not None and doi_elem.text:
                paper["doi"] = doi_elem.text

            papers.append(paper)

        logger.info(f"  arXiv/{category}: {len(papers)} papers")
        return papers

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean whitespace from text."""
        return " ".join(text.split())
