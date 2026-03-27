#!/usr/bin/env python3
"""
Weight Manager - 管理关键词权重的自适应学习系统

修改版：
- 支持 bootstrap 模式统计
- 记录投票次数用于自动切换模式
- 优化的权重调整算法
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Tuple

logger = logging.getLogger(__name__)


class WeightManager:
    """管理关键词权重，支持投票反馈学习。"""
    
    def __init__(self, keywords_path: str):
        """
        初始化权重管理器。
        
        Args:
            keywords_path: keywords.json 文件路径
        """
        self.keywords_path = keywords_path
        self.data = self._load_or_init()
    
    def _load_or_init(self) -> dict:
        """加载现有数据或初始化新数据。"""
        if os.path.exists(self.keywords_path):
            try:
                with open(self.keywords_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded {len(data.get('keywords', {}))} keywords from {self.keywords_path}")
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading keywords file: {e}")
        
        # 初始化数据结构
        return {
            "keywords": {},
            "stats": {
                "total_votes": 0,
                "votes_by_type": {
                    "not_interested": 0,
                    "neutral": 0,
                    "very_relevant": 0
                },
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "deactivated_keywords": [],  # 被停用的关键词
        }
    
    def _save(self):
        """保存数据到文件。"""
        self.data["stats"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        os.makedirs(os.path.dirname(self.keywords_path), exist_ok=True)
        with open(self.keywords_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def get_keywords(self) -> dict:
        """获取所有活跃的关键词及其权重。"""
        return self.data.get("keywords", {})
    
    def add_keyword(self, keyword: str, weight: float = 1.0, source: str = "manual"):
        """
        添加新关键词。
        
        Args:
            keyword: 关键词
            weight: 初始权重
            source: 来源（manual, bootstrap, vote_derived）
        """
        keyword_lower = keyword.lower().strip()
        
        if keyword_lower in self.data["keywords"]:
            logger.debug(f"Keyword '{keyword_lower}' already exists")
            return
        
        self.data["keywords"][keyword_lower] = {
            "weight": weight,
            "source": source,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "vote_count": 0,
        }
        self._save()
        logger.info(f"Added keyword '{keyword_lower}' with weight {weight}")
    
    def add_keywords_batch(self, keywords: list[str], weight: float = 1.0, source: str = "bootstrap"):
        """批量添加关键词。"""
        for kw in keywords:
            keyword_lower = kw.lower().strip()
            if keyword_lower and keyword_lower not in self.data["keywords"]:
                self.data["keywords"][keyword_lower] = {
                    "weight": weight,
                    "source": source,
                    "added_at": datetime.now(timezone.utc).isoformat(),
                    "vote_count": 0,
                }
        self._save()
        logger.info(f"Added {len(keywords)} keywords in batch")
    
    def score_paper(self, paper: dict) -> Tuple[float, list[str]]:
        """
        计算论文的相关性分数。
        
        Args:
            paper: 论文字典，包含 title 和 abstract
            
        Returns:
            (总分数, 匹配的关键词列表)
        """
        title = paper.get("title", "").lower()
        abstract = paper.get("abstract", "").lower()
        text = f"{title} {abstract}"
        
        score = 0.0
        matched = []
        
        for keyword, info in self.data.get("keywords", {}).items():
            weight = info.get("weight", 1.0) if isinstance(info, dict) else info
            
            # 跳过负权重关键词
            if weight <= 0:
                continue
            
            if keyword in text:
                score += weight
                matched.append(keyword)
        
        return score, matched
    
    def process_vote(self, paper_id: str, vote_type: str, matched_keywords: list[str], 
                     config: dict = None):
        """
        处理用户投票，更新相关关键词的权重。
        
        Args:
            paper_id: 论文 ID
            vote_type: 投票类型 (not_interested, neutral, very_relevant)
            matched_keywords: 该论文匹配的关键词列表
            config: 配置字典，包含投票分数值
        """
        config = config or {}
        vote_values = config.get("weights", {}).get("vote_values", {})
        
        # 默认投票分数
        vote_deltas = {
            "not_interested": vote_values.get("not_interested", -0.3),
            "neutral": vote_values.get("neutral", 0),
            "very_relevant": vote_values.get("very_relevant", 0.5),
        }
        
        max_weight = config.get("weights", {}).get("max_weight", 5.0)
        min_weight = config.get("weights", {}).get("min_weight", -2.0)
        
        delta = vote_deltas.get(vote_type, 0)
        
        if delta == 0:
            # 中立投票不改变权重
            self._record_vote(vote_type)
            return
        
        # 更新匹配关键词的权重
        for keyword in matched_keywords:
            if keyword in self.data["keywords"]:
                info = self.data["keywords"][keyword]
                if isinstance(info, dict):
                    old_weight = info.get("weight", 1.0)
                    new_weight = max(min_weight, min(max_weight, old_weight + delta))
                    info["weight"] = new_weight
                    info["vote_count"] = info.get("vote_count", 0) + 1
                    info["last_voted"] = datetime.now(timezone.utc).isoformat()
                    logger.info(f"Keyword '{keyword}': {old_weight:.2f} → {new_weight:.2f} ({vote_type})")
        
        self._record_vote(vote_type)
        self._save()
    
    def _record_vote(self, vote_type: str):
        """记录投票统计。"""
        self.data["stats"]["total_votes"] = self.data["stats"].get("total_votes", 0) + 1
        
        votes_by_type = self.data["stats"].setdefault("votes_by_type", {})
        votes_by_type[vote_type] = votes_by_type.get(vote_type, 0) + 1
    
    def apply_daily_decay(self, weights_config: dict):
        """
        应用每日权重衰减。
        
        长时间未被投票的关键词会逐渐降低权重。
        """
        decay_rate = weights_config.get("daily_decay", 0.02)
        min_threshold = weights_config.get("min_threshold", 0.1)
        
        if decay_rate <= 0:
            return
        
        deactivated = []
        
        for keyword, info in list(self.data.get("keywords", {}).items()):
            if isinstance(info, dict):
                old_weight = info.get("weight", 1.0)
                
                # 只对正权重应用衰减
                if old_weight > 0:
                    new_weight = old_weight * (1 - decay_rate)
                    
                    # 检查是否低于阈值
                    if new_weight < min_threshold:
                        # 移到停用列表
                        deactivated.append({
                            "keyword": keyword,
                            "final_weight": new_weight,
                            "deactivated_at": datetime.now(timezone.utc).isoformat(),
                        })
                        del self.data["keywords"][keyword]
                        logger.info(f"Keyword '{keyword}' deactivated (weight {new_weight:.3f} < {min_threshold})")
                    else:
                        info["weight"] = new_weight
        
        if deactivated:
            self.data.setdefault("deactivated_keywords", []).extend(deactivated)
        
        self._save()
        logger.info(f"Applied daily decay ({decay_rate}), {len(deactivated)} keywords deactivated")
    
    def get_stats(self) -> dict:
        """获取统计信息。"""
        keywords = self.data.get("keywords", {})
        
        return {
            "total_keywords": len(keywords),
            "active_keywords": sum(1 for k, v in keywords.items() 
                                   if isinstance(v, dict) and v.get("weight", 0) > 0),
            "total_votes": self.data.get("stats", {}).get("total_votes", 0),
            "votes_by_type": self.data.get("stats", {}).get("votes_by_type", {}),
            "deactivated_count": len(self.data.get("deactivated_keywords", [])),
        }
    
    def export_keywords(self) -> list[dict]:
        """导出关键词列表用于调试。"""
        result = []
        for keyword, info in self.data.get("keywords", {}).items():
            if isinstance(info, dict):
                result.append({
                    "keyword": keyword,
                    "weight": info.get("weight", 1.0),
                    "vote_count": info.get("vote_count", 0),
                    "source": info.get("source", "unknown"),
                })
            else:
                result.append({
                    "keyword": keyword,
                    "weight": info,
                    "vote_count": 0,
                    "source": "legacy",
                })
        
        # 按权重排序
        result.sort(key=lambda x: x["weight"], reverse=True)
        return result
