import unittest
from unittest.mock import Mock, patch

from main import analyze_papers
from src.analyzer import GeminiAnalyzer
from src.content_extractor import PaperContentExtractor


class FakeResponse:
    def __init__(self, payload: bytes, content_type: str, url: str):
        self._payload = payload
        self.headers = {"Content-Type": content_type}
        self._url = url

    def read(self):
        return self._payload

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class PaperContentExtractorTests(unittest.TestCase):
    def test_pdf_extraction_uses_first_pages(self):
        extractor = PaperContentExtractor({"max_pdf_pages": 2, "max_chars": 1000})
        paper = {"id": "1234.5678", "source": "arxiv", "pdf_url": "https://example.org/paper.pdf"}

        page1 = Mock()
        page1.extract_text.return_value = "First page body"
        page2 = Mock()
        page2.extract_text.return_value = "Second page body"
        page3 = Mock()
        page3.extract_text.return_value = "Third page body"

        with patch(
            "src.content_extractor.urllib.request.urlopen",
            return_value=FakeResponse(b"%PDF-1.4 fake", "application/pdf", paper["pdf_url"]),
        ), patch(
            "src.content_extractor.PdfReader",
            return_value=Mock(pages=[page1, page2, page3]),
        ):
            result = extractor.enrich_paper(paper)

        self.assertEqual(result["content_source"], "pdf")
        self.assertEqual(result["content"], "First page body Second page body")

    def test_html_extraction_collects_meta_and_paragraphs(self):
        extractor = PaperContentExtractor({"max_chars": 1000})
        html = b"""
        <html>
          <head>
            <meta name="description" content="A concise summary of the article.">
          </head>
          <body>
            <article>
              <h1>Paper Title</h1>
              <p>This paragraph contains enough content to pass the readability threshold for extraction.</p>
              <p>This is another paragraph with additional paper details and method descriptions for testing.</p>
            </article>
          </body>
        </html>
        """

        with patch(
            "src.content_extractor.urllib.request.urlopen",
            return_value=FakeResponse(html, "text/html; charset=utf-8", "https://example.org/paper"),
        ):
            result = extractor.enrich_paper({"id": "paper-1", "url": "https://example.org/paper"})

        self.assertEqual(result["content_source"], "html")
        self.assertIn("A concise summary of the article.", result["content"])
        self.assertIn("This paragraph contains enough content", result["content"])

    def test_prompt_prefers_extracted_content_when_available(self):
        analyzer = GeminiAnalyzer()
        prompt = analyzer._build_prompt(
            {
                "title": "Test Paper",
                "abstract": "Abstract fallback",
                "content": "Detailed extracted paper body",
                "content_source": "pdf",
                "matched_keywords": ["quantum"],
            },
            language="en",
        )

        self.assertIn("Detailed extracted paper body", prompt)
        self.assertIn("Prioritize this extracted content", prompt)


class AnalyzePapersIntegrationTests(unittest.TestCase):
    def test_analyze_papers_enriches_content_before_calling_ai(self):
        class StubAnalyzer:
            def __init__(self):
                self.seen_content = []

            def analyze(self, paper, language="en"):
                self.seen_content.append((paper.get("content"), language))
                return "ok"

        class StubExtractor:
            def __init__(self, _config):
                pass

            def enrich_paper(self, paper):
                paper["content"] = "Expanded body"
                paper["content_source"] = "pdf"
                return paper

        analyzer = StubAnalyzer()
        config = {
            "ai_provider": "gemini",
            "email": {"language": "en"},
            "content_extraction": {"enabled": True},
        }

        with patch("main.get_analyzer", return_value=analyzer), patch("main.PaperContentExtractor", StubExtractor):
            papers = analyze_papers([{"id": "p1", "title": "Demo", "abstract": "Short"}], config)

        self.assertEqual(papers[0]["ai_summary"], "ok")
        self.assertEqual(analyzer.seen_content, [("Expanded body", "en")])


if __name__ == "__main__":
    unittest.main()
