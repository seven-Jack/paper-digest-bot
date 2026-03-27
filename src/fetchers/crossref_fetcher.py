"""
CrossRef Fetcher - Fetch papers from CrossRef API.

CrossRef has 140M+ papers with DOI metadata.
Free API, polite pool available with email.
"""

import json
import logging
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class CrossRefFetcher:
    """Fetch papers from CrossRef API."""

    BASE_URL = "https://api.crossref.org"

    def __init__(self, keywords: list[str] = None, journals: list[str] = None):
        """
        Initialize the fetcher.
        
        Args:
            keywords: List of keywords to search
            journals: List of journal ISSNs to filter by
        """
        self.keywords = keywords or []
        self.journals = journals or []
        self.email = os.environ.get("CROSSREF_EMAIL", "")

    def fetch(self, days_back: int = 7, max_results: int = 100) -> list[dict]:
        """
        Fetch recent papers from CrossRef.
        
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
                logger.info(f"  CrossRef/{keyword}: {len(results)} papers")
            except Exception as e:
                logger.error(f"Failed to fetch CrossRef for '{keyword}': {e}")

        # Search by journal ISSN
        for issn in self.journals:
            try:
                results = self._search_by_journal(issn, cutoff_str, max_results)
                papers.extend(results)
                logger.info(f"  CrossRef/ISSN:{issn}: {len(results)} papers")
            except Exception as e:
                logger.error(f"Failed to fetch CrossRef for journal '{issn}': {e}")

        # Deduplicate by DOI
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
            "rows": min(limit, 1000),
            "filter": f"from-pub-date:{date_from}",
            "sort": "published",
            "order": "desc",
        }
        
        url = f"{self.BASE_URL}/works?{urllib.parse.urlencode(params)}"
        return self._fetch_and_parse(url)

    def _search_by_journal(self, issn: str, date_from: str, limit: int) -> list[dict]:
        """Search papers by journal ISSN."""
        params = {
            "rows": min(limit, 1000),
            "filter": f"from-pub-date:{date_from},issn:{issn}",
            "sort": "published",
            "order": "desc",
        }
        
        url = f"{self.BASE_URL}/works?{urllib.parse.urlencode(params)}"
        return self._fetch_and_parse(url)

    def _fetch_and_parse(self, url: str) -> list[dict]:
        """Fetch URL and parse results into paper dicts."""
        headers = {
            "Accept": "application/json",
        }
        
        # Add email for polite pool
        if self.email:
            headers["User-Agent"] = f"PaperDigestBot/1.0 (mailto:{self.email})"
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}mailto={urllib.parse.quote(self.email)}"
        else:
            headers["User-Agent"] = "PaperDigestBot/1.0"

        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())

        papers = []
        for item in data.get("message", {}).get("items", []):
            title_list = item.get("title", [])
            title = title_list[0] if title_list else ""
            
            abstract = item.get("abstract", "")
            # Clean HTML from abstract
            if abstract:
                import re
                abstract = re.sub(r'<[^>]+>', '', abstract)
            
            if not title:
                continue

            # Parse authors
            authors = []
            for author in item.get("author", []):
                given = author.get("given", "")
                family = author.get("family", "")
                if given and family:
                    authors.append(f"{given} {family}")
                elif family:
                    authors.append(family)

            # Get DOI
            doi = item.get("DOI", "")

            # Get publication date
            pub_date = ""
            date_parts = item.get("published", {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                parts = date_parts[0]
                if len(parts) >= 3:
                    pub_date = f"{parts[0]}-{parts[1]:02d}-{parts[2]:02d}"
                elif len(parts) >= 2:
                    pub_date = f"{parts[0]}-{parts[1]:02d}"
                elif len(parts) >= 1:
                    pub_date = str(parts[0])

            # Get URL
            url = item.get("URL", "")
            if not url and doi:
                url = f"https://doi.org/{doi}"

            # Get journal/venue
            venue = ""
            container = item.get("container-title", [])
            if container:
                venue = container[0]

            paper = {
                "id": f"cr:{doi}" if doi else f"cr:{hash(title)}",
                "title": title.strip(),
                "abstract": abstract.strip(),
                "authors": authors[:10],
                "url": url,
                "published": pub_date,
                "source": "CrossRef",
                "doi": doi,
                "venue": venue,
                "type": item.get("type", ""),
            }
            papers.append(paper)

        return papers
