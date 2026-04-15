#!/usr/bin/env python3
"""
Semantic Scholar Fetcher - 从 Semantic Scholar API 获取学术论文

Semantic Scholar 是一个免费的学术搜索引擎，由 Allen Institute for AI 维护。
API 文档: https://api.semanticscholar.org/
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class SemanticScholarFetcher:
    """Fetch papers from Semantic Scholar API."""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, fields_of_study: list[str] = None, keywords: list[str] = None):
        """
        初始化 Semantic Scholar fetcher.
        
        Args:
            fields_of_study: 学科领域列表，如 ["Physics", "Computer Science"]
            keywords: 搜索关键词列表
        """
        self.fields_of_study = fields_of_study or []
        self.keywords = keywords or []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PaperDigestBot/1.0 (Academic Research Tool)"
        })
    
    def fetch(self, days_back: int = 2, max_results: int = 50) -> list[dict]:
        """
        获取最近发表的论文。
        
        Args:
            days_back: 获取最近几天的论文
            max_results: 最大返回数量
            
        Returns:
            论文列表，每篇论文包含 id, title, abstract, authors, url, published, source, doi
        """
        papers = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        # 使用关键词搜索
        for keyword in self.keywords:
            try:
                keyword_papers = self._search_by_keyword(keyword, max_results // len(self.keywords) if self.keywords else max_results)
                papers.extend(keyword_papers)
                time.sleep(1)  # Rate limiting: 100 requests per 5 minutes
            except Exception as e:
                logger.error(f"Error fetching from Semantic Scholar for keyword '{keyword}': {e}")
        
        # 去重（基于论文 ID）
        seen_ids = set()
        unique_papers = []
        for paper in papers:
            if paper["id"] not in seen_ids:
                seen_ids.add(paper["id"])
                unique_papers.append(paper)
        
        logger.info(f"Semantic Scholar: fetched {len(unique_papers)} unique papers")
        return unique_papers[:max_results]
    
    def _search_by_keyword(self, keyword: str, limit: int = 20) -> list[dict]:
        """按关键词搜索论文."""
        url = f"{self.BASE_URL}/paper/search"
        
        params = {
            "query": keyword,
            "limit": min(limit, 100),  # API 限制
            "fields": "paperId,title,abstract,authors,year,venue,publicationDate,externalIds,url,citationCount,openAccessPdf",
            "fieldsOfStudy": ",".join(self.fields_of_study) if self.fields_of_study else None,
        }
        
        # 移除 None 值
        params = {k: v for k, v in params.items() if v is not None}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"Semantic Scholar API error: {e}")
            return []
        
        papers = []
        for item in data.get("data", []):
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)
        
        return papers
    
    def _parse_paper(self, item: dict) -> Optional[dict]:
        """解析 API 返回的论文数据."""
        paper_id = item.get("paperId")
        title = item.get("title")
        abstract = item.get("abstract")
        
        if not paper_id or not title:
            return None
        
        # 提取作者
        authors = []
        for author in item.get("authors", []):
            name = author.get("name")
            if name:
                authors.append(name)
        
        # 提取 DOI
        external_ids = item.get("externalIds", {})
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")
        open_access_pdf = (item.get("openAccessPdf") or {}).get("url")
        
        # 构建 URL
        if doi:
            url = f"https://doi.org/{doi}"
        elif arxiv_id:
            url = f"https://arxiv.org/abs/{arxiv_id}"
        else:
            url = item.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"
        
        # 解析发布日期
        pub_date = item.get("publicationDate")
        if pub_date:
            try:
                published = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                published = datetime.now(timezone.utc)
        else:
            published = datetime.now(timezone.utc)
        
        return {
            "id": f"s2:{paper_id}",
            "title": title,
            "abstract": abstract or "(No abstract available)",
            "authors": authors,
            "url": url,
            "published": published.isoformat(),
            "source": "Semantic Scholar",
            "doi": doi,
            "venue": item.get("venue", ""),
            "citation_count": item.get("citationCount", 0),
            "pdf_url": open_access_pdf,
        }
