"""
Skill: duplicate_detection

Cross-references a PR's title/body/linked-issue against recently closed
issues and PRs to flag likely duplicates. Uses lightweight keyword
overlap rather than embeddings — intentionally simple and explainable
for a 2-week build; swapping in a real embedding-similarity model is a
documented "next step" in the writeup.
"""

import re
from typing import Any

STOPWORDS = {
    "the", "a", "an", "in", "on", "for", "to", "of", "and", "is", "this",
    "that", "fix", "fixes", "bug", "issue", "pr", "add", "added", "update",
    "updated", "with", "from", "by", "when", "it", "was", "were",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    return {w for w in words if w not in STOPWORDS}


def evaluate(pr: dict[str, Any], closed_items: list[dict[str, Any]]) -> dict[str, Any]:
    linked_issue = pr.get("linked_issue")

    # Strongest signal: PR explicitly links an issue that's already closed via another PR
    if linked_issue:
        for item in closed_items:
            if item["number"] == linked_issue and item.get("state") == "closed":
                return {
                    "skill": "duplicate_detection",
                    "is_likely_duplicate": True,
                    "confidence": 0.9,
                    "matched_item": item["number"],
                    "reason": f"linked issue #{linked_issue} is already closed",
                }

    # Weaker signal: keyword overlap between PR title and closed item titles.
    # IMPORTANT: only items that are actually CLOSED count as "duplicate" evidence.
    # A high-overlap match against a still-OPEN issue almost certainly means this
    # PR *is the fix* for that issue (exactly what happened with the CSV-injection
    # PR in our own test data) — that should never be flagged as a duplicate.
    pr_keywords = _keywords(pr.get("title", "") + " " + (pr.get("body") or ""))
    best_closed_match = None
    best_closed_overlap = 0
    best_open_match = None
    best_open_overlap = 0

    for item in closed_items:
        item_keywords = _keywords(item["title"])
        if not item_keywords:
            continue
        overlap = len(pr_keywords & item_keywords) / max(len(item_keywords), 1)
        if item.get("state") == "closed":
            if overlap > best_closed_overlap:
                best_closed_overlap = overlap
                best_closed_match = item
        else:
            if overlap > best_open_overlap:
                best_open_overlap = overlap
                best_open_match = item

    if best_closed_match and best_closed_overlap >= 0.5:
        return {
            "skill": "duplicate_detection",
            "is_likely_duplicate": True,
            "confidence": round(best_closed_overlap, 2),
            "matched_item": best_closed_match["number"],
            "reason": f"title/body overlaps significantly with already-closed item #{best_closed_match['number']} ({best_closed_match['title']!r})",
        }

    if best_open_match and best_open_overlap >= 0.5:
        return {
            "skill": "duplicate_detection",
            "is_likely_duplicate": False,
            "confidence": round(best_open_overlap, 2),
            "matched_item": best_open_match["number"],
            "reason": f"likely resolves open issue #{best_open_match['number']} ({best_open_match['title']!r}) — suggest linking, not a duplicate",
        }

    return {
        "skill": "duplicate_detection",
        "is_likely_duplicate": False,
        "confidence": 0.0,
        "matched_item": None,
        "reason": "no strong match against recently closed or open issues/PRs",
    }
