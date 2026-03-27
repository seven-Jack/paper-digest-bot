"""
OpenAlex Fetcher - Fetch papers from OpenAlex API.

OpenAlex has 250M+ papers, completely free and open.
Polite pool: include email in User-Agent for higher rate limits.
"""

import json
import logging
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class OpenAlexFetcher:
    """Fetch papers from OpenAlex API."""

    BASE_URL = "https://api.openalex.org"

    # OpenAlex concept IDs for common fields
    # Find more at: https://api.openalex.org/concepts?search=
    CONCEPT_IDS = {
        "physics": "C121332964",
        "quantum physics": "C62520636",
        "atomic physics": "C191897082",
        "condensed matter": "C33923547",
        "optics": "C108827166",
        "computer science": "C41008148",
        "artificial intelligence": "C154945302",
        "machine learning": "C119857082",
        "biology": "C86803240",
        "chemistry": "C185592680",
        "materials science": "C192562407",
        "mathematics": "C33923547",
        "medicine": "C71924100",
        "neuroscience": "C134018914",
    }

    def __init__(self, concepts: list[str] = None, keywords: list[str] = None):
        """
        Initialize the fetcher.
        
        Args:
            concepts: List of concept names like ["physics", "quantum physics"]
            keywords: List of keywords to search in title/abstract
        """
        self.concepts = concepts or []
        self.keywords = keywords or []
        self.email = os.environ.get("OPENALEX_EMAIL", "")

    def fetch(self, days_back: int = 7, max_results: int = 100) -> list[dict]:
        """
        Fetch recent papers from OpenAlex.
        
        Args:
            days_back: Number of days to look back
            max_results: Maximum number of papers to fetch per query
            
        Returns:
            List of paper dicts
        """
        papers = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")

        # Search by concepts
        for concept in self.concepts:
            try:
                concept_id = self.CONCEPT_IDS.get(concept.lower())
                if concept_id:
                    results = self._search_by_concept(concept_id, cutoff_str, max_results)
                else:
                    # Try searching by concept name
                    results = self._search_by_keyword(concept, cutoff_str, max_results)
                papers.extend(results)
                logger.info(f"  OpenAlex/{concept}: {len(results)} papers")
            except Exception as e:
                logger.error(f"Failed to fetch OpenAlex for concept '{concept}': {e}")

        # Search by keywords
        for keyword in self.keywords:
            try:
                results = self._search_by_keyword(keyword, cutoff_str, max_results)
                papers.extend(results)
                logger.info(f"  OpenAlex/{keyword}: {len(results)} papers")
            except Exception as e:
                logger.error(f"Failed to fetch OpenAlex for keyword '{keyword}': {e}")

        # Deduplicate by paper ID
        seen_ids = set()
        unique_papers = []
        for paper in papers:
            if paper["id"] not in seen_ids:
                seen_ids.add(paper["id"])
                unique_papers.append(paper)

        return unique_papers

    def _search_by_concept(self, concept_id: str, date_from: str, limit: int) -> list[dict]:
        """Search papers by OpenAlex concept ID."""
        params = {
            "filter": f"concepts.id:{concept_id},from_publication_date:{date_from}",
            "per_page": min(limit, 200),
            "sort": "publication_date:desc",
        }
        
        url = f"{self.BASE_URL}/works?{urllib.parse.urlencode(params)}"
        return self._fetch_and_parse(url)

    def _search_by_keyword(self, keyword: str, date_from: str, limit: int) -> list[dict]:
        """Search papers by keyword in title/abstract."""
        params = {
            "search": keyword,
            "filter": f"from_publication_date:{date_from}",
            "per_page": min(limit, 200),
            "sort": "publication_date:desc",
        }
        
        url = f"{self.BASE_URL}/works?{urllib.parse.urlencode(params)}"
        return self._fetch_and_parse(url)

    def _fetch_and_parse(self, url: str) -> list[dict]:
        """Fetch URL and parse results into paper dicts."""
        # Add email for polite pool (higher rate limits)
        if self.email:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}mailto={urllib.parse.quote(self.email)}"

        headers = {
            "Accept": "application/json",
            "User-Agent": f"PaperDigestBot/1.0 (mailto:{self.email})" if self.email else "PaperDigestBot/1.0",
        }

        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        papers = []
        for item in data.get("results", []):
            title = item.get("title", "")
            
            # Get abstract from inverted index if available
            abstract = ""
            abstract_inverted = item.get("abstract_inverted_index")
            if abstract_inverted:
                abstract = self._reconstruct_abstract(abstract_inverted)
            
            if not title:
                continue

            # Extract DOI
            doi = item.get("doi", "")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")

            # Parse authors
            authors = []
            for authorship in item.get("authorships", []):
                author = authorship.get("author", {})
                if author.get("display_name"):
                    authors.append(author["display_name"])

            # Get OpenAlex ID
            openalex_id = item.get("id", "")
            if openalex_id.startswith("https://openalex.org/"):
                openalex_id = openalex_id.replace("https://openalex.org/", "")

            # Get best URL
            url = item.get("primary_location", {}).get("landing_page_url", "")
            if not url:
                url = item.get("doi", "") or f"https://openalex.org/{openalex_id}"

            paper = {
                "id": f"oa:{openalex_id}",
                "title": title.strip(),
                "abstract": abstract.strip(),
                "authors": authors[:10],  # Limit to first 10 authors
                "url": url,
                "published": item.get("publication_date", ""),
                "source": "OpenAlex",
                "doi": doi,
                "venue": item.get("primary_location", {}).get("source", {}).get("display_name", ""),
                "cited_by_count": item.get("cited_by_count", 0),
                "open_access": item.get("open_access", {}).get("is_oa", False),
            }
            papers.append(paper)

        return papers

    def _reconstruct_abstract(self, inverted_index: dict) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ""
        
        # Create position -> word mapping
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        
        # Sort by position and join
        word_positions.sort(key=lambda x: x[0])
        return " ".join(word for _, word in word_positions)
