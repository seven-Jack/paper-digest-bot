"""
PubMed Fetcher - Fetch papers from NCBI PubMed API.

PubMed has 35M+ biomedical papers.
Free API with E-utilities.
"""

import json
import logging
import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class PubMedFetcher:
    """Fetch papers from PubMed API."""

    SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def __init__(self, keywords: list[str] = None, mesh_terms: list[str] = None):
        """
        Initialize the fetcher.
        
        Args:
            keywords: List of keywords to search
            mesh_terms: List of MeSH terms to filter by
        """
        self.keywords = keywords or []
        self.mesh_terms = mesh_terms or []
        self.api_key = os.environ.get("PUBMED_API_KEY", "")
        self.email = os.environ.get("PUBMED_EMAIL", "")

    def fetch(self, days_back: int = 7, max_results: int = 100) -> list[dict]:
        """
        Fetch recent papers from PubMed.
        
        Args:
            days_back: Number of days to look back
            max_results: Maximum number of papers to fetch per query
            
        Returns:
            List of paper dicts
        """
        papers = []

        # Search by keywords
        for keyword in self.keywords:
            try:
                results = self._search_and_fetch(keyword, days_back, max_results)
                papers.extend(results)
                logger.info(f"  PubMed/{keyword}: {len(results)} papers")
            except Exception as e:
                logger.error(f"Failed to fetch PubMed for '{keyword}': {e}")

        # Search by MeSH terms
        for mesh in self.mesh_terms:
            try:
                query = f"{mesh}[MeSH Terms]"
                results = self._search_and_fetch(query, days_back, max_results)
                papers.extend(results)
                logger.info(f"  PubMed/MeSH:{mesh}: {len(results)} papers")
            except Exception as e:
                logger.error(f"Failed to fetch PubMed for MeSH '{mesh}': {e}")

        # Deduplicate by PMID
        seen_ids = set()
        unique_papers = []
        for paper in papers:
            if paper["id"] not in seen_ids:
                seen_ids.add(paper["id"])
                unique_papers.append(paper)

        return unique_papers

    def _search_and_fetch(self, query: str, days_back: int, max_results: int) -> list[dict]:
        """Search PubMed and fetch paper details."""
        # Step 1: Search for PMIDs
        pmids = self._search(query, days_back, max_results)
        if not pmids:
            return []

        # Step 2: Fetch paper details
        return self._fetch_details(pmids)

    def _search(self, query: str, days_back: int, max_results: int) -> list[str]:
        """Search PubMed and return list of PMIDs."""
        # Add date filter
        full_query = f"({query}) AND (\"last {days_back} days\"[PDat])"
        
        params = {
            "db": "pubmed",
            "term": full_query,
            "retmax": min(max_results, 10000),
            "retmode": "json",
            "sort": "pub_date",
        }
        
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email

        url = f"{self.SEARCH_URL}?{urllib.parse.urlencode(params)}"
        
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        return data.get("esearchresult", {}).get("idlist", [])

    def _fetch_details(self, pmids: list[str]) -> list[dict]:
        """Fetch paper details for given PMIDs."""
        if not pmids:
            return []

        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email

        url = f"{self.FETCH_URL}?{urllib.parse.urlencode(params)}"
        
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=60) as resp:
            xml_data = resp.read()

        return self._parse_xml(xml_data)

    def _parse_xml(self, xml_data: bytes) -> list[dict]:
        """Parse PubMed XML response into paper dicts."""
        papers = []
        
        try:
            root = ET.fromstring(xml_data)
        except ET.ParseError as e:
            logger.error(f"Failed to parse PubMed XML: {e}")
            return []

        for article in root.findall(".//PubmedArticle"):
            try:
                paper = self._parse_article(article)
                if paper:
                    papers.append(paper)
            except Exception as e:
                logger.warning(f"Failed to parse article: {e}")
                continue

        return papers

    def _parse_article(self, article) -> dict | None:
        """Parse a single PubmedArticle element."""
        medline = article.find(".//MedlineCitation")
        if medline is None:
            return None

        # Get PMID
        pmid_elem = medline.find(".//PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""
        if not pmid:
            return None

        # Get title
        title_elem = medline.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None else ""
        if not title:
            return None

        # Get abstract
        abstract_parts = []
        for abstract_text in medline.findall(".//AbstractText"):
            if abstract_text.text:
                label = abstract_text.get("Label", "")
                if label:
                    abstract_parts.append(f"{label}: {abstract_text.text}")
                else:
                    abstract_parts.append(abstract_text.text)
        abstract = " ".join(abstract_parts)

        # Get authors
        authors = []
        for author in medline.findall(".//Author"):
            last_name = author.find("LastName")
            fore_name = author.find("ForeName")
            if last_name is not None and last_name.text:
                if fore_name is not None and fore_name.text:
                    authors.append(f"{fore_name.text} {last_name.text}")
                else:
                    authors.append(last_name.text)

        # Get publication date
        pub_date = ""
        date_elem = medline.find(".//PubDate")
        if date_elem is not None:
            year = date_elem.find("Year")
            month = date_elem.find("Month")
            day = date_elem.find("Day")
            if year is not None and year.text:
                pub_date = year.text
                if month is not None and month.text:
                    # Convert month name to number if needed
                    month_map = {
                        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                        "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                        "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
                    }
                    month_str = month_map.get(month.text, month.text.zfill(2))
                    pub_date = f"{pub_date}-{month_str}"
                    if day is not None and day.text:
                        pub_date = f"{pub_date}-{day.text.zfill(2)}"

        # Get journal
        journal_elem = medline.find(".//Journal/Title")
        venue = journal_elem.text if journal_elem is not None else ""

        # Get DOI
        doi = ""
        for article_id in article.findall(".//ArticleId"):
            if article_id.get("IdType") == "doi":
                doi = article_id.text or ""
                break

        return {
            "id": f"pm:{pmid}",
            "title": title.strip(),
            "abstract": abstract.strip(),
            "authors": authors[:10],
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "published": pub_date,
            "source": "PubMed",
            "doi": doi,
            "venue": venue,
            "pmid": pmid,
        }
