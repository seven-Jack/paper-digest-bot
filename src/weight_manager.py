"""
Weight Manager - Adaptive keyword weight system.

Handles:
- Scoring papers against weighted keywords
- Applying daily weight decay
- Processing user votes to update weights
- Deactivating keywords below threshold
"""

import json
import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class WeightManager:
    """Manage keyword weights with adaptive feedback loop."""

    def __init__(self, keywords_path: str):
        self.path = keywords_path
        self.data = self._load()

    def _load(self) -> dict:
        """Load keywords from JSON file."""
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"metadata": {}, "keywords": {}}

    def save(self):
        """Save keywords to JSON file."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get_active_keywords(self) -> dict[str, float]:
        """Return keywords with weight above 0."""
        return {
            kw: info["weight"]
            for kw, info in self.data.get("keywords", {}).items()
            if info.get("weight", 0) > 0
        }

    def score_paper(self, paper: dict) -> tuple[float, list[str]]:
        """
        Score a paper based on keyword matches in title and abstract.
        Returns (score, list_of_matched_keywords).
        """
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
        total_score = 0.0
        matched = []

        for keyword, info in self.data.get("keywords", {}).items():
            weight = info.get("weight", 0)
            if weight <= 0:
                continue

            # Case-insensitive search with word boundary awareness
            pattern = re.escape(keyword.lower())
            if re.search(pattern, text):
                # Title matches are worth 2x
                title_text = paper.get("title", "").lower()
                multiplier = 2.0 if re.search(pattern, title_text) else 1.0
                total_score += weight * multiplier
                matched.append(keyword)

        return total_score, matched

    def apply_daily_decay(self, weight_config: dict):
        """Apply daily weight decay to all keywords and deactivate low ones."""
        decay_rate = weight_config.get("daily_decay", 0.02)
        min_threshold = weight_config.get("min_threshold", 0.1)
        deactivated = []

        for kw, info in self.data.get("keywords", {}).items():
            old_weight = info.get("weight", 0)
            if old_weight <= 0:
                continue

            new_weight = old_weight - decay_rate
            if new_weight < min_threshold:
                new_weight = 0
                deactivated.append(kw)

            info["weight"] = round(new_weight, 4)

        if deactivated:
            logger.info(f"Deactivated keywords below threshold: {deactivated}")

        self.save()

    def process_vote(self, paper_id: str, vote: str, matched_keywords: list[str],
                     vote_config: dict):
        """
        Process a user vote and update keyword weights.

        Args:
            paper_id: Unique ID of the voted paper
            vote: One of 'not_interested', 'neutral', 'very_relevant'
            matched_keywords: Keywords that matched this paper
            vote_config: Vote value configuration
        """
        vote_values = vote_config.get("vote_values", {
            "not_interested": -2,
            "neutral": 0,
            "very_relevant": 3,
        })

        value = vote_values.get(vote, 0)
        if value == 0:
            return

        # Distribute vote value across matched keywords
        if not matched_keywords:
            return

        per_keyword = value / len(matched_keywords)
        now = datetime.now(timezone.utc).isoformat()

        for kw in matched_keywords:
            if kw in self.data.get("keywords", {}):
                info = self.data["keywords"][kw]
                old_weight = info.get("weight", 0)

                # Apply vote adjustment (scale: vote value * 0.1)
                adjustment = per_keyword * 0.1
                new_weight = max(0, old_weight + adjustment)
                info["weight"] = round(new_weight, 4)

                # Record vote
                info.setdefault("votes", []).append({
                    "paper_id": paper_id,
                    "vote": vote,
                    "value": per_keyword,
                    "timestamp": now,
                })
                # Keep only last 50 votes per keyword
                info["votes"] = info["votes"][-50:]
                info["last_voted"] = now

        self.save()
        logger.info(f"Vote '{vote}' processed for paper {paper_id}, "
                    f"affected keywords: {matched_keywords}")

    def add_keywords(self, keywords: list[dict], initial_weight: float = 1.0):
        """
        Add new keywords from DOI bootstrap.

        Args:
            keywords: List of dicts with 'keyword' and 'category' keys
            initial_weight: Starting weight for new keywords
        """
        added = []
        for kw_info in keywords:
            keyword = kw_info.get("keyword", "").strip()
            if not keyword:
                continue
            if keyword not in self.data.setdefault("keywords", {}):
                self.data["keywords"][keyword] = {
                    "weight": initial_weight,
                    "category": kw_info.get("category", "general"),
                    "source": "doi_bootstrap",
                    "votes": [],
                    "last_matched": None,
                    "added_at": datetime.now(timezone.utc).isoformat(),
                }
                added.append(keyword)

        if added:
            self.save()
            logger.info(f"Added {len(added)} new keywords: {added}")

    def get_stats(self) -> dict:
        """Return statistics about keyword weights."""
        keywords = self.data.get("keywords", {})
        active = {k: v for k, v in keywords.items() if v.get("weight", 0) > 0}
        inactive = {k: v for k, v in keywords.items() if v.get("weight", 0) <= 0}

        return {
            "total": len(keywords),
            "active": len(active),
            "inactive": len(inactive),
            "top_5": sorted(
                active.items(),
                key=lambda x: x[1].get("weight", 0),
                reverse=True,
            )[:5],
        }
