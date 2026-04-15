#!/usr/bin/env python3
"""
OpenAlex Fetcher - 从 OpenAlex API 获取学术论文

OpenAlex 是一个完全免费、开放的学术图谱，包含超过 2.5 亿篇论文。
API 文档: https://docs.openalex.org/
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class OpenAlexFetcher:
    """Fetch papers from OpenAlex API."""
    
    BASE_URL = "https://api.openalex.org"
    
    def __init__(self, concepts: list[str] = None, keywords: list[str] = None, 
                 email: str = None):
        """
        初始化 OpenAlex fetcher.
        
        Args:
            concepts: OpenAlex concept IDs 列表，如 ["C62520636"] (Quantum mechanics)
            keywords: 搜索关键词列表
            email: 用于 polite pool（可选，但推荐）
        """
        self.concepts = concepts or []
        self.keywords = keywords or []
        self.session = requests.Session()
        
        # OpenAlex 推荐在请求中包含邮箱以获得更高的速率限制
        headers = {"User-Agent": "PaperDigestBot/1.0 (Academic Research Tool)"}
        if email:
            headers["User-Agent"] += f"; mailto:{email}"
        self.session.headers.update(headers)
    
    def fetch(self, days_back: int = 2, max_results: int = 50) -> list[dict]:
        """
        获取最近发表的论文。
        
        Args:
            days_back: 获取最近几天的论文
            max_results: 最大返回数量
            
        Returns:
            论文列表
        """
        papers = []
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        from_date = cutoff_date.strftime("%Y-%m-%d")
        
        # 方法1：按概念搜索
        if self.concepts:
            for concept_id in self.concepts:
                try:
                    concept_papers = self._fetch_by_concept(concept_id, from_date, max_results // len(self.concepts))
                    papers.extend(concept_papers)
                    time.sleep(0.2)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error fetching OpenAlex concept {concept_id}: {e}")
        
        # 方法2：按关键词搜索
        if self.keywords:
            for keyword in self.keywords:
                try:
                    keyword_papers = self._fetch_by_keyword(keyword, from_date, max_results // len(self.keywords) if self.keywords else max_results)
                    papers.extend(keyword_papers)
                    time.sleep(0.2)
                except Exception as e:
                    logger.error(f"Error fetching OpenAlex keyword '{keyword}': {e}")
        
        # 去重
        seen_ids = set()
        unique_papers = []
        for paper in papers:
            if paper["id"] not in seen_ids:
                seen_ids.add(paper["id"])
                unique_papers.append(paper)
        
        logger.info(f"OpenAlex: fetched {len(unique_papers)} unique papers")
        return unique_papers[:max_results]
    
    def _fetch_by_concept(self, concept_id: str, from_date: str, per_page: int = 25) -> list[dict]:
        """按 OpenAlex concept 获取论文."""
        # 标准化 concept ID
        if not concept_id.startswith("C"):
            concept_id = f"C{concept_id}"
        
        url = f"{self.BASE_URL}/works"
        params = {
            "filter": f"concepts.id:{concept_id},from_publication_date:{from_date}",
            "sort": "publication_date:desc",
            "per_page": min(per_page, 200),
            "select": "id,doi,title,abstract_inverted_index,authorships,publication_date,primary_location,best_oa_location,cited_by_count",
        }
        
        return self._fetch_works(url, params)
    
    def _fetch_by_keyword(self, keyword: str, from_date: str, per_page: int = 25) -> list[dict]:
        """按关键词搜索论文."""
        url = f"{self.BASE_URL}/works"
        params = {
            "search": keyword,
            "filter": f"from_publication_date:{from_date}",
            "sort": "publication_date:desc",
            "per_page": min(per_page, 200),
            "select": "id,doi,title,abstract_inverted_index,authorships,publication_date,primary_location,best_oa_location,cited_by_count",
        }
        
        return self._fetch_works(url, params)
    
    def _fetch_works(self, url: str, params: dict) -> list[dict]:
        """执行 API 请求并解析结果."""
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"OpenAlex API error: {e}")
            return []
        
        papers = []
        for item in data.get("results", []):
            paper = self._parse_paper(item)
            if paper:
                papers.append(paper)
        
        return papers
    
    def _parse_paper(self, item: dict) -> Optional[dict]:
        """解析 API 返回的论文数据."""
        work_id = item.get("id", "").replace("https://openalex.org/", "")
        title = item.get("title")
        
        if not work_id or not title:
            return None
        
        # OpenAlex 使用 inverted index 存储摘要，需要重建
        abstract = self._reconstruct_abstract(item.get("abstract_inverted_index", {}))
        
        # 提取作者
        authors = []
        for authorship in item.get("authorships", []):
            author_info = authorship.get("author", {})
            name = author_info.get("display_name")
            if name:
                authors.append(name)
        
        # 提取 DOI
        doi = item.get("doi", "").replace("https://doi.org/", "") if item.get("doi") else None
        
        # 构建 URL
        primary_location = item.get("primary_location", {}) or {}
        best_oa_location = item.get("best_oa_location", {}) or {}
        landing_page_url = primary_location.get("landing_page_url")
        pdf_url = (
            primary_location.get("pdf_url")
            or best_oa_location.get("pdf_url")
            or best_oa_location.get("landing_page_url")
        )
        
        if doi:
            url = f"https://doi.org/{doi}"
        elif landing_page_url:
            url = landing_page_url
        else:
            url = f"https://openalex.org/{work_id}"
        
        # 解析发布日期
        pub_date = item.get("publication_date")
        if pub_date:
            try:
                published = datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                published = datetime.now(timezone.utc)
        else:
            published = datetime.now(timezone.utc)
        
        # 获取来源/期刊名
        source = primary_location.get("source", {}) or {}
        venue = source.get("display_name", "")
        
        return {
            "id": f"oa:{work_id}",
            "title": title,
            "abstract": abstract or "(No abstract available)",
            "authors": authors[:10],  # 限制作者数量
            "url": url,
            "published": published.isoformat(),
            "source": f"OpenAlex ({venue})" if venue else "OpenAlex",
            "doi": doi,
            "venue": venue,
            "citation_count": item.get("cited_by_count", 0),
            "pdf_url": pdf_url,
        }
    
    def _reconstruct_abstract(self, inverted_index: dict) -> str:
        """
        从 OpenAlex 的 inverted index 格式重建摘要文本。
        
        OpenAlex 存储格式: {"word": [position1, position2, ...], ...}
        """
        if not inverted_index:
            return ""
        
        # 构建位置到单词的映射
        position_word = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                position_word[pos] = word
        
        # 按位置排序并重建文本
        if not position_word:
            return ""
        
        max_pos = max(position_word.keys())
        words = [position_word.get(i, "") for i in range(max_pos + 1)]
        
        return " ".join(words)
