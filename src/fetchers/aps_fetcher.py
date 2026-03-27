"""Fetch recent papers from APS journals via RSS/Atom feeds."""

import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# APS provides RSS feeds for recent articles
APS_FEED_URLS = {
    "prl": "https://feeds.aps.org/rss/recent/prl.xml",
    "pra": "https://feeds.aps.org/rss/recent/pra.xml",
    "prx": "https://feeds.aps.org/rss/recent/prx.xml",
    "prresearch": "https://feeds.aps.org/rss/recent/prresearch.xml",
    "prxquantum": "https://feeds.aps.org/rss/recent/prxquantum.xml",
}


class APSFetcher:
    """Fetch papers from APS journal RSS feeds."""

    def __init__(self, journals: list[str]):
        self.journals = journals or ["prl", "pra"]

    def fetch(self, days_back: int = 2) -> list[dict]:
        """Fetch recent papers from APS journals."""
        papers = []
        for journal in self.journals:
            if journal not in APS_FEED_URLS:
                logger.warning(f"Unknown APS journal: {journal}, skipping")
                continue
            try:
                papers.extend(self._fetch_journal(journal, days_back))
            except Exception as e:
                logger.error(f"Failed to fetch APS/{journal}: {e}")
        return papers

    def _fetch_journal(self, journal: str, days_back: int) -> list[dict]:
        """Fetch papers from a single APS journal RSS feed."""
        url = APS_FEED_URLS[journal]
        logger.info(f"Fetching APS/{journal}...")

        req = urllib.request.Request(url, headers={"User-Agent": "PaperDigestBot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()

        root = ET.fromstring(data)
        papers = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        # RSS format: <channel> -> <item>
        for item in root.iter("item"):
            pub_date_str = item.findtext("pubDate", "")
            if pub_date_str:
                try:
                    # RSS date format: "Thu, 06 Mar 2025 00:00:00 -0500"
                    from email.utils import parsedate_to_datetime
                    pub_date = parsedate_to_datetime(pub_date_str)
                    if pub_date < cutoff:
                        continue
                except Exception:
                    pass

            title = self._clean_text(item.findtext("title", ""))
            link = item.findtext("link", "")
            description = self._clean_text(item.findtext("description", ""))

            # Extract DOI from link
            doi = ""
            if "doi.org/" in link:
                doi = link.split("doi.org/")[-1]
            elif "/doi/" in link:
                doi = link.split("/doi/")[-1]

            paper = {
                "id": f"aps_{journal}_{doi.replace('/', '_')}",
                "title": title,
                "abstract": description,
                "authors": self._extract_authors(item),
                "url": link,
                "published": pub_date_str,
                "source": f"aps/{journal}",
                "category": journal,
                "doi": doi,
            }
            papers.append(paper)

        logger.info(f"  APS/{journal}: {len(papers)} papers")
        return papers

    @staticmethod
    def _extract_authors(item) -> list[str]:
        """Extract author names from RSS item."""
        # APS RSS uses dc:creator
        authors = []
        for creator in item.iter("{http://purl.org/dc/elements/1.1/}creator"):
            if creator.text:
                authors.append(creator.text.strip())
        if not authors:
            creator_text = item.findtext("{http://purl.org/dc/elements/1.1/}creator", "")
            if creator_text:
                authors = [a.strip() for a in creator_text.split(",")]
        return authors

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean whitespace and HTML tags from text."""
        import re
        text = re.sub(r"<[^>]+>", "", text)
        return " ".join(text.split())
