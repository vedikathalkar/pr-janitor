"""
Skill: spam_detection

Detects low-effort / farming-pattern PRs commonly seen during high-volume
contribution events (GSSoC, Hacktoberfest). Each rule is intentionally
small and explainable — the classifier agent reports *why* a PR was
flagged, never just a bare score, so maintainers can override false
positives quickly.
"""

from typing import Any

TRIVIAL_FILES = {"README.md", "CONTRIBUTORS.md", "CONTRIBUTING.md"}


def evaluate(pr: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    score = 0.0

    files = set(pr.get("files_changed") or [])
    additions = pr.get("additions") or 0
    deletions = pr.get("deletions") or 0
    total_diff = additions + deletions

    # Rule 1: trivial-file-only edits with no linked issue
    if files and files.issubset(TRIVIAL_FILES) and not pr.get("linked_issue"):
        reasons.append("only touches trivial files (README/CONTRIBUTORS) with no linked issue")
        score += 0.4

    # Rule 2: tiny diff with no body explanation
    body = (pr.get("body") or "").strip()
    if total_diff <= 4 and len(body) < 15:
        reasons.append("diff is trivially small and PR description is empty or near-empty")
        score += 0.3

    # Rule 3: high cross-repo PR velocity from a brand-new account (farming signal)
    account_age_days = pr.get("_account_age_days")
    velocity = pr.get("author_total_prs_all_repos_30d")
    if velocity and velocity >= 15:
        reasons.append(f"author opened {velocity} PRs across repos in the last 30 days (farming signal)")
        score += 0.3
    if pr.get("author_total_prs_this_repo") == 1 and velocity and velocity >= 10:
        reasons.append("first-time contributor to this repo but high contribution velocity elsewhere")
        score += 0.2

    # Rule 4: generic/copy-pasted commit message patterns
    commit_msgs = pr.get("commit_messages") or []
    generic_patterns = {"update readme.md", "fix typo", "minor fix", "added my name to contributors"}
    if any(msg.strip().lower() in generic_patterns for msg in commit_msgs):
        reasons.append("commit message matches a known generic/low-effort pattern")
        score += 0.2

    score = min(score, 1.0)
    return {
        "skill": "spam_detection",
        "spam_score": round(score, 2),
        "is_likely_spam": score >= 0.5,
        "reasons": reasons,
    }
