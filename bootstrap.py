#!/usr/bin/env python3
"""
DOI Bootstrap - Extract research keywords from reference papers.

Usage:
  python bootstrap.py --dois "10.1103/PhysRevA.111.053107,10.1103/ntv1-8d5w"
  python bootstrap.py --dois "10.1103/PhysRevA.111.053107" --ai gemini
"""

import argparse
import json
import logging
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def fetch_crossref(doi: str) -> dict | None:
    """Fetch paper metadata from CrossRef API."""
    url = f"https://api.crossref.org/works/{doi}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "PaperDigestBot/1.0 (mailto:paper-digest@example.com)"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("message", {})
    except Exception as e:
        logger.warning(f"CrossRef lookup failed for {doi}: {e}")
        return None


def extract_keywords_rule_based(metadata: dict) -> list[dict]:
    """Extract keywords from paper metadata using pattern matching."""
    keywords = []

    # Use subject/keywords from CrossRef
    for subj in metadata.get("subject", []):
        keywords.append({"keyword": subj.strip(), "category": "subject"})

    # Extract from title
    title = " ".join(metadata.get("title", []))
    for kw in _extract_physics_terms(title):
        keywords.append({"keyword": kw, "category": "title_term"})

    # Extract from abstract (strip JATS XML)
    abstract = re.sub(r"<[^>]+>", "", metadata.get("abstract", ""))
    for kw in _extract_physics_terms(abstract):
        if kw not in [k["keyword"] for k in keywords]:
            keywords.append({"keyword": kw, "category": "abstract_term"})

    return keywords


# AMO physics terms and common computational methods
_PHYSICS_PATTERNS = [
    r"coupled[- ]cluster",
    r"configuration interaction",
    r"many[- ]body perturbation",
    r"Dirac[- ]Coulomb(?:[- ](?:Gaunt|Breit))?",
    r"Fock[- ]space",
    r"equation[- ]of[- ]motion",
    r"optical clock",
    r"highly charged ions?",
    r"polarizabilit(?:y|ies)",
    r"isotope shifts?",
    r"hyperfine structure",
    r"transition energ(?:y|ies)",
    r"field shift",
    r"superheavy element",
    r"g[- ]?factor",
    r"quadrupole moment",
    r"QED correction",
    r"Lamb shift",
    r"Breit interaction",
    r"electron correlation",
    r"excitation energ(?:y|ies)",
    r"ionization potential",
    r"atomic structure",
    r"dipole (?:moment|polarizability)",
    r"oscillator strength",
    r"branching ratio",
    r"Rydberg",
    r"ultracold",
    r"Bose[- ]Einstein",
    r"Feshbach resonance",
    r"scattering length",
    r"photoionization",
    r"autoionization",
    r"parity violation",
    r"relativistic\s+(?:correction|effect|calculation|method)",
    r"MCDHF",
    r"CI\+MBPT",
    r"FSCC",
    r"EOM[- ]RCC",
    r"KRCI",
    r"basis[- ]set",
    r"Gaunt interaction",
    r"Breit interaction",
    r"nuclear recoil",
    r"Drake[- ]type",
    r"Hylleraas",
    r"explicitly correlated",
    r"B[- ]spline",
]


def _extract_physics_terms(text: str) -> list[str]:
    """Extract physics terms from text using pattern matching."""
    found = []
    text_lower = text.lower()
    for pat in _PHYSICS_PATTERNS:
        matches = re.findall(pat, text_lower)
        for m in matches:
            clean = m.strip()
            if clean and clean not in found and len(clean) > 3:
                found.append(clean)
    return found[:20]


def extract_keywords_ai(metadata: dict, provider: str) -> list[dict]:
    """Use AI to extract keywords from paper metadata."""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from src.analyzer import get_analyzer
    except ImportError:
        logger.warning("Could not import analyzer module, falling back to rule-based.")
        return []

    analyzer = get_analyzer(provider)
    if analyzer is None:
        return []

    title = " ".join(metadata.get("title", []))
    abstract = re.sub(r"<[^>]+>", "", metadata.get("abstract", ""))

    prompt = (
        "You are an expert in atomic and molecular physics. Given this paper, "
        "extract 8-15 specific research keywords/phrases for finding similar papers. "
        "Focus on: methods, physical systems, properties, and applications.\n\n"
        f"Title: {title}\n"
        f"Abstract: {abstract}\n\n"
        "Return ONLY a JSON array: "
        '[{"keyword": "...", "category": "method|system|property|application|field"}]'
    )

    try:
        # Borrow the analyzer's API to call with our custom prompt
        paper = {"title": prompt, "abstract": "", "matched_keywords": []}
        result = analyzer.analyze(paper, language="en")
        json_match = re.search(r"\[.*\]", result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.warning(f"AI keyword extraction failed: {e}")

    return []


def bootstrap(dois: list[str], output_path: str, ai_provider: str = ""):
    """Main bootstrap function."""
    all_keywords = []
    doi_list = []

    for doi in dois:
        doi = doi.strip()
        if not doi:
            continue
        logger.info(f"Processing DOI: {doi}")
        doi_list.append(doi)

        metadata = fetch_crossref(doi)
        if metadata is None:
            logger.warning(f"  No metadata found for {doi}")
            continue

        title = " ".join(metadata.get("title", []))
        logger.info(f"  Title: {title}")

        # Try AI first, fall back to rule-based
        keywords = []
        if ai_provider:
            keywords = extract_keywords_ai(metadata, ai_provider)
            if keywords:
                logger.info(f"  AI extracted {len(keywords)} keywords")

        if not keywords:
            keywords = extract_keywords_rule_based(metadata)
            logger.info(f"  Rule-based extracted {len(keywords)} keywords")

        all_keywords.extend(keywords)

    # Deduplicate
    seen = set()
    unique = []
    for kw in all_keywords:
        key = kw["keyword"].lower().strip()
        if key not in seen and len(key) > 2:
            seen.add(key)
            unique.append(kw)

    # Build keywords.json
    data = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "bootstrap_dois": doi_list,
            "version": "1.0",
        },
        "keywords": {},
    }
    for kw in unique:
        data["keywords"][kw["keyword"]] = {
            "weight": 1.0,
            "category": kw.get("category", "general"),
            "source": "doi_bootstrap",
            "votes": [],
            "last_matched": None,
        }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"\n{'='*50}")
    logger.info(f"Bootstrap complete!")
    logger.info(f"  DOIs processed: {len(doi_list)}")
    logger.info(f"  Keywords extracted: {len(unique)}")
    logger.info(f"  Saved to: {output_path}")
    logger.info(f"{'='*50}")
    for kw in unique:
        logger.info(f"  [{kw.get('category', '?'):12s}] {kw['keyword']}")


def main():
    parser = argparse.ArgumentParser(description="Bootstrap keywords from DOI references")
    parser.add_argument("--dois", required=True, help="Comma-separated DOI list")
    parser.add_argument("--output", default="data/keywords.json", help="Output file path")
    parser.add_argument("--ai", default="", help="AI provider for extraction (gemini/openai/claude)")
    args = parser.parse_args()

    dois = [d.strip() for d in args.dois.split(",") if d.strip()]
    if not dois:
        print("Error: No DOIs provided.")
        sys.exit(1)

    bootstrap(dois, args.output, args.ai)


if __name__ == "__main__":
    main()
