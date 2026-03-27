#!/usr/bin/env python3
"""
Weight Manager - 管理关键词权重的自适应学习系统
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Tuple

logger = logging.getLogger(__name__)


class WeightManager:
    def __init__(self, keywords_path: str):
        self.keywords_path = keywords_path
        self.data = self._load_or_init()
    
    def _load_or_init(self) -> dict:
        if os.path.exists(self.keywords_path):
            try:
                with open(self.keywords_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Loaded {len(data.get('keywords', {}))} keywords from {self.keywords_path}")
                if "stats" not in data:
                    data["stats"] = {"total_votes": 0, "votes_by_type": {}, "last_updated": datetime.now(timezone.utc).isoformat()}
                if "deactivated_keywords" not in data:
                    data["deactivated_keywords"] = []
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading keywords file: {e}")
        return {"keywords": {}, "stats": {"total_votes": 0, "votes_by_type": {}}, "deactivated_keywords": []}
    
    def _save(self):
        if "stats" not in self.data:
            self.data["stats"] = {}
        self.data["stats"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        os.makedirs(os.path.dirname(self.keywords_path), exist_ok=True)
        with open(self.keywords_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    def get_keywords(self) -> dict:
        return self.data.get("keywords", {})
    
    def score_paper(self, paper: dict) -> Tuple[float, list[str]]:
        title = paper.get("title", "").lower()
        abstract = paper.get("abstract", "").lower()
        text = f"{title} {abstract}"
        score = 0.0
        matched = []
        for keyword, info in self.data.get("keywords", {}).items():
            weight = info.get("weight", 1.0) if isinstance(info, dict) else info
            if weight <= 0:
                continue
            if keyword in text:
                score += weight
                matched.append(keyword)
        return score, matched
    
    def apply_daily_decay(self, weights_config: dict):
        decay_rate = weights_config.get("daily_decay", 0.02)
        min_threshold = weights_config.get("min_threshold", 0.1)
        if decay_rate <= 0:
            return
        deactivated = []
        for keyword, info in list(self.data.get("keywords", {}).items()):
            if isinstance(info, dict):
                old_weight = info.get("weight", 1.0)
            else:
                old_weight = info
                self.data["keywords"][keyword] = {"weight": old_weight, "source": "legacy"}
                info = self.data["keywords"][keyword]
            if old_weight > 0:
                new_weight = old_weight * (1 - decay_rate)
                if new_weight < min_threshold:
                    deactivated.append(keyword)
                    del self.data["keywords"][keyword]
                else:
                    info["weight"] = new_weight
        if "deactivated_keywords" not in self.data:
            self.data["deactivated_keywords"] = []
        self.data["deactivated_keywords"].extend(deactivated)
        self._save()
        logger.info(f"Applied daily decay ({decay_rate}), {len(deactivated)} keywords deactivated")
