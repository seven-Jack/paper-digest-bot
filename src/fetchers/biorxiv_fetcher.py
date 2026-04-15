"""
bioRxiv/medRxiv Fetcher - Fetch preprints from bioRxiv and medRxiv.

bioRxiv: Biology preprints
medRxiv: Medical preprints
Both are free and open access.
"""

import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class BioRxivFetcher:
    """Fetch papers from bioRxiv and medRxiv APIs."""

    BASE_URL = "https://api.biorxiv.org"

    def __init__(self, servers: list[str] = None, subjects: list[str] = None):
        """
        Initialize the fetcher.
        
        Args:
            servers: List of servers to fetch from ["biorxiv", "medrxiv"]
            subjects: List of subjects/categories to filter by
        """
        self.servers = servers or ["biorxiv", "medrxiv"]
        self.subjects = subjects or []

    def fetch(self, days_back: int = 7, max_results: int = 100) -> list[dict]:
        """
        Fetch recent preprints from bioRxiv/medRxiv.
        
        Args:
            days_back: Number of days to look back
            max_results: Maximum number of papers to fetch per server
            
        Returns:
            List of paper dicts
        """
        papers = []
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        for server in self.servers:
            try:
                results = self._fetch_server(server, start_str, end_str, max_results)
                papers.extend(results)
                logger.info(f"  {server}: {len(results)} papers")
            except Exception as e:
                logger.error(f"Failed to fetch {server}: {e}")

        return papers

    def _fetch_server(self, server: str, start_date: str, end_date: str, max_results: int) -> list[dict]:
        """Fetch papers from a specific server."""
        # bioRxiv API: /details/[server]/[interval]/[cursor]
        # interval format: YYYY-MM-DD/YYYY-MM-DD
        
        papers = []
        cursor = 0
        
        while len(papers) < max_results:
            url = f"{self.BASE_URL}/details/{server}/{start_date}/{end_date}/{cursor}"
            
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                break

            collection = data.get("collection", [])
            if not collection:
                break

            for item in collection:
                paper = self._parse_paper(item, server)
                if paper:
                    # Filter by subject if specified
                    if self.subjects:
                        paper_subject = paper.get("category", "").lower()
                        if not any(s.lower() in paper_subject for s in self.subjects):
                            continue
                    papers.append(paper)

            # Check for more results
            messages = data.get("messages", [])
            total = 0
            for msg in messages:
                if msg.get("status") == "ok":
                    total = msg.get("total", 0)
                    cursor = msg.get("cursor", 0)
                    break
            
            if cursor == 0 or len(papers) >= max_results:
                break

        return papers[:max_results]

    def _parse_paper(self, item: dict, server: str) -> dict | None:
        """Parse a single paper from bioRxiv API response."""
        doi = item.get("doi", "")
        title = item.get("title", "")
        
        if not title or not doi:
            return None

        # Parse authors (format: "Last, First; Last, First")
        authors_str = item.get("authors", "")
        authors = []
        if authors_str:
            for author in authors_str.split(";"):
                author = author.strip()
                if author:
                    # Convert "Last, First" to "First Last"
                    parts = author.split(",")
                    if len(parts) == 2:
                        authors.append(f"{parts[1].strip()} {parts[0].strip()}")
                    else:
                        authors.append(author)

        return {
            "id": f"biorxiv:{doi}",
            "title": title.strip(),
            "abstract": item.get("abstract", "").strip(),
            "authors": authors[:10],
            "url": f"https://doi.org/{doi}",
            "published": item.get("date", ""),
            "source": server.capitalize(),
            "doi": doi,
            "venue": server.capitalize(),
            "category": item.get("category", ""),
            "version": item.get("version", "1"),
            "pdf_url": f"https://www.{server}.org/content/{doi}v{item.get('version', '1')}.full.pdf",
        }
