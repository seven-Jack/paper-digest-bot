"""Load and validate configuration from YAML file."""

import os
import yaml


def load_config(path: str = "config.yaml") -> dict:
    """Load config from YAML file, falling back to example if needed."""
    if not os.path.exists(path):
        example = path.replace(".yaml", ".example.yaml")
        if os.path.exists(example):
            path = example
        else:
            return _default_config()

    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    return {**_default_config(), **config}


def _default_config() -> dict:
    return {
        "ai_provider": "gemini",
        "email": {
            "language": "zh",
            "max_papers": 20,
            "schedule_utc": "00:00",
        },
        "content_extraction": {
            "enabled": True,
            "max_chars": 12000,
            "max_pdf_pages": 4,
            "timeout_seconds": 30,
        },
        "sources": {
            "arxiv": {"enabled": True, "categories": ["physics.atom-ph", "quant-ph"]},
            "aps": {"enabled": True, "journals": ["prl", "pra"]},
            "nature": {"enabled": False, "journals": []},
            "science": {"enabled": False, "journals": []},
        },
        "weights": {
            "vote_values": {"not_interested": -2, "neutral": 0, "very_relevant": 3},
            "daily_decay": 0.02,
            "min_threshold": 0.1,
            "initial_weight": 1.0,
        },
    }
