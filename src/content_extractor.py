"""Best-effort paper content extraction for AI analysis."""

from __future__ import annotations

import io
import logging
import re
import urllib.request
from html import unescape

from pypdf import PdfReader

logger = logging.getLogger(__name__)

USER_AGENT = "PaperDigestBot/1.0"


class PaperContentExtractor:
    """Fetch and extract readable paper content from PDF or HTML sources."""

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.enabled = config.get("enabled", True)
        self.max_chars = int(config.get("max_chars", 12000))
        self.max_pdf_pages = int(config.get("max_pdf_pages", 4))
        self.timeout_seconds = int(config.get("timeout_seconds", 30))

    def enrich_paper(self, paper: dict) -> dict:
        """Attach extracted content to a paper dict when possible."""
        if not self.enabled or paper.get("content"):
            return paper

        for url, source_kind in self._candidate_urls(paper):
            try:
                content = self._extract_from_url(url)
            except Exception as exc:
                logger.debug("Content extraction failed for %s: %s", url, exc)
                continue

            if content:
                paper["content"] = content
                paper["content_source"] = source_kind
                paper["content_url"] = url
                logger.info(
                    "Extracted %s content for %s",
                    source_kind,
                    paper.get("id", paper.get("title", "paper")),
                )
                return paper

        logger.info(
            "No readable full text found for %s, falling back to abstract",
            paper.get("id", paper.get("title", "paper")),
        )
        return paper

    def _candidate_urls(self, paper: dict) -> list[tuple[str, str]]:
        """Build the most promising URLs for content extraction."""
        candidates: list[tuple[str, str]] = []
        seen = set()

        def add(url: str | None, source_kind: str):
            if not url:
                return
            normalized = url.strip()
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            candidates.append((normalized, source_kind))

        add(paper.get("pdf_url"), "pdf")
        add(paper.get("open_access_pdf_url"), "pdf")

        derived_pdf = self._derive_pdf_url(paper)
        add(derived_pdf, "pdf")

        add(paper.get("url"), "html")

        doi = (paper.get("doi") or "").strip()
        if doi:
            add(f"https://doi.org/{doi}", "html")

        return candidates

    def _derive_pdf_url(self, paper: dict) -> str | None:
        """Derive a PDF URL for sources with predictable patterns."""
        paper_url = (paper.get("url") or "").strip()
        paper_id = (paper.get("id") or "").strip()
        source = (paper.get("source") or "").lower()

        if paper.get("pdf_url"):
            return paper.get("pdf_url")

        if "arxiv" in source or "arxiv.org" in paper_url:
            arxiv_id = paper_id
            if "/abs/" in paper_url:
                arxiv_id = paper_url.rsplit("/abs/", 1)[-1]
            elif paper_id.startswith("arxiv:"):
                arxiv_id = paper_id.split(":", 1)[-1]
            if arxiv_id:
                return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        if source in {"biorxiv", "medrxiv"} and paper.get("doi"):
            version = paper.get("version", "1")
            return f"https://www.{source}.org/content/{paper['doi']}v{version}.full.pdf"

        return None

    def _extract_from_url(self, url: str) -> str:
        """Download a URL and extract text based on its content type."""
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/pdf,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            payload = resp.read()
            headers = getattr(resp, "headers", {})
            content_type = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
            final_url = resp.geturl() if hasattr(resp, "geturl") else url

        if self._looks_like_pdf(final_url, content_type, payload):
            return self._extract_pdf_text(payload)

        html = payload.decode("utf-8", errors="ignore")
        return self._extract_html_text(html)

    @staticmethod
    def _looks_like_pdf(url: str, content_type: str, payload: bytes) -> bool:
        return (
            url.lower().endswith(".pdf")
            or "application/pdf" in content_type.lower()
            or payload.startswith(b"%PDF")
        )

    def _extract_pdf_text(self, payload: bytes) -> str:
        """Extract text from the first few pages of a PDF."""
        reader = PdfReader(io.BytesIO(payload))
        pages = []

        for index, page in enumerate(reader.pages):
            if index >= self.max_pdf_pages:
                break
            text = self._normalize_text(page.extract_text() or "")
            if text:
                pages.append(text)

        return self._truncate("\n\n".join(pages))

    def _extract_html_text(self, html: str) -> str:
        """Extract the most relevant readable text from an HTML page."""
        if not html:
            return ""

        cleaned_html = re.sub(
            r"<(script|style|noscript|svg)[^>]*>.*?</\1>",
            " ",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        chunks = []
        meta_patterns = [
            r'<meta[^>]+name=["\']citation_abstract["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+name=["\']dc\.description["\'][^>]+content=["\'](.*?)["\']',
        ]
        for pattern in meta_patterns:
            chunks.extend(re.findall(pattern, cleaned_html, flags=re.IGNORECASE | re.DOTALL))

        body_match = (
            re.search(r"<article\b[^>]*>(.*?)</article>", cleaned_html, flags=re.IGNORECASE | re.DOTALL)
            or re.search(r"<main\b[^>]*>(.*?)</main>", cleaned_html, flags=re.IGNORECASE | re.DOTALL)
            or re.search(r"<body\b[^>]*>(.*?)</body>", cleaned_html, flags=re.IGNORECASE | re.DOTALL)
        )
        body = body_match.group(1) if body_match else cleaned_html

        chunks.extend(re.findall(r"<h[1-3]\b[^>]*>(.*?)</h[1-3]>", body, flags=re.IGNORECASE | re.DOTALL))
        chunks.extend(re.findall(r"<p\b[^>]*>(.*?)</p>", body, flags=re.IGNORECASE | re.DOTALL))

        readable = []
        seen = set()
        for chunk in chunks:
            text = self._strip_html(chunk)
            if len(text) < 25 or text in seen:
                continue
            seen.add(text)
            readable.append(text)

        return self._truncate("\n\n".join(readable))

    def _strip_html(self, html_fragment: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html_fragment)
        return self._normalize_text(unescape(text))

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _truncate(self, text: str) -> str:
        text = self._normalize_text(text)
        if len(text) <= self.max_chars:
            return text

        truncated = text[: self.max_chars].rsplit(" ", 1)[0].strip()
        return f"{truncated}..."
