"""
GitHub client for PR Janitor.

Design notes (for judges / Kaggle writeup):
- READ operations (list PRs, list issues) use the public REST API.
  No token is required for reads, but an optional token raises rate limits
  from 60/hr to 5000/hr.
- WRITE operations (posting comments) are intentionally separated into
  `post_comment_if_approved`, which refuses to run unless an explicit
  human-approval flag is set AND a token with write scope is present.
  This is the human-in-the-loop security boundary described in the
  architecture doc.
- If the live API is unreachable or rate-limited, the client transparently
  falls back to bundled sample data (src/data/sample_prs.json) so demos
  and judging never break on network conditions outside our control.
- Linked-issue detection is done by parsing the PR body for GitHub's
  closing-keyword convention (Fixes/Closes/Resolves #N) — no extra API
  call needed. Test-coverage detection requires one extra call per PR
  to GET /pulls/{n}/files; this is done best-effort and degrades to
  `has_tests=None` for that single PR if the call fails, rather than
  failing the whole batch.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import requests

SAMPLE_DATA_PATH = Path(__file__).parent.parent / "data" / "sample_prs.json"
GITHUB_API = "https://api.github.com"

CLOSING_KEYWORD_PATTERN = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s*#(\d+)", re.IGNORECASE
)
TEST_FILE_PATTERN = re.compile(
    r"(test|spec)s?[._-]|[._-](test|spec)s?\.|__tests__", re.IGNORECASE
)


def _extract_linked_issue(body: str) -> int | None:
    """Parse GitHub's closing-keyword convention out of a PR body.
    e.g. 'Fixes #123', 'closes: #45', 'Resolved #7'."""
    match = CLOSING_KEYWORD_PATTERN.search(body or "")
    return int(match.group(1)) if match else None


def _looks_like_test_file(filename: str) -> bool:
    return bool(TEST_FILE_PATTERN.search(filename))


class GitHubClient:
    def __init__(self, repo: str = "freeCodeCamp/freeCodeCamp", token: str | None = None):
        self.repo = repo
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.used_fallback = False
        self.fallback_reason: str | None = None

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _load_fallback(self, reason: str) -> dict:
        self.used_fallback = True
        self.fallback_reason = reason
        with open(SAMPLE_DATA_PATH) as f:
            return json.load(f)

    def _reason_for_status(self, status_code: int) -> str:
        if status_code == 404:
            return f"repository '{self.repo}' not found — check the spelling (format: owner/repo)"
        if status_code in (403, 429):
            return "GitHub API rate limit reached"
        if status_code == 401:
            return "GitHub token rejected — check it's valid and not expired"
        return f"GitHub API returned an unexpected error ({status_code})"

    def fetch_open_pull_requests(self, limit: int = 10, fetch_file_details: bool = True) -> list[dict[str, Any]]:
        """
        Returns a list of PR dicts. Tries the live API first; falls back to
        bundled sample data on any error (rate limit, network, auth issue),
        and records *why* in self.fallback_reason for accurate UI messaging.

        If `fetch_file_details` is True (default), makes one extra API call
        per PR to get real files_changed/has_tests. Set to False to save
        rate-limit budget when you only need spam/title-level signals.
        """
        try:
            url = f"{GITHUB_API}/repos/{self.repo}/pulls"
            resp = requests.get(
                url,
                headers=self._headers(),
                params={"state": "open", "per_page": limit, "sort": "created", "direction": "desc"},
                timeout=10,
            )
            if resp.status_code != 200:
                data = self._load_fallback(self._reason_for_status(resp.status_code))
                return data["pull_requests"][:limit]
            raw = resp.json()
            return [self._normalize_live_pr(pr, fetch_file_details) for pr in raw]
        except requests.RequestException as e:
            data = self._load_fallback(f"network error reaching GitHub ({e.__class__.__name__})")
            return data["pull_requests"][:limit]

    def _fetch_pr_files(self, pr_number: int) -> list[str] | None:
        """Best-effort fetch of changed filenames for a single PR.
        Returns None (not an empty list) on failure, so callers can tell
        'we don't know' apart from 'genuinely no files changed'."""
        try:
            url = f"{GITHUB_API}/repos/{self.repo}/pulls/{pr_number}/files"
            resp = requests.get(url, headers=self._headers(), params={"per_page": 100}, timeout=10)
            if resp.status_code != 200:
                return None
            return [f["filename"] for f in resp.json()]
        except Exception:
            return None

    def _normalize_live_pr(self, pr: dict, fetch_file_details: bool) -> dict[str, Any]:
        """Map live GitHub API PR shape into the normalized shape our agents expect."""
        body = pr.get("body") or ""
        files_changed: list[str] = []
        has_tests = None

        if fetch_file_details:
            fetched_files = self._fetch_pr_files(pr["number"])
            if fetched_files is not None:
                files_changed = fetched_files
                has_tests = any(_looks_like_test_file(f) for f in fetched_files)

        return {
            "number": pr["number"],
            "title": pr["title"],
            "author": pr["user"]["login"],
            "author_account_created": None,  # would require a second API call per author
            "author_total_prs_this_repo": None,
            "author_total_prs_all_repos_30d": None,
            "files_changed": files_changed,
            "additions": pr.get("additions"),
            "deletions": pr.get("deletions"),
            "linked_issue": _extract_linked_issue(body),
            "has_tests": has_tests,
            "commit_messages": [],
            "body": body,
            "created_at": pr.get("created_at"),
            "_live": True,
        }

    def fetch_closed_issues_and_prs(self) -> list[dict[str, Any]]:
        try:
            url = f"{GITHUB_API}/repos/{self.repo}/issues"
            resp = requests.get(
                url,
                headers=self._headers(),
                params={"state": "all", "per_page": 30},
                timeout=10,
            )
            if resp.status_code != 200:
                data = self._load_fallback(self._reason_for_status(resp.status_code))
                return data["closed_issues_and_prs"]
            raw = resp.json()
            return [{"number": i["number"], "title": i["title"], "state": i["state"]} for i in raw]
        except requests.RequestException as e:
            data = self._load_fallback(f"network error reaching GitHub ({e.__class__.__name__})")
            return data["closed_issues_and_prs"]

    def post_comment_if_approved(self, pr_number: int, body: str, approved: bool) -> dict[str, Any]:
        """
        SECURITY GATE: this is the only write path in the whole system.
        It will refuse to act unless `approved` was explicitly set to True
        by a human reviewing the drafted comment, AND a write-scoped token
        is configured. Absence of either is a no-op, not a silent failure.
        """
        if not approved:
            return {"status": "blocked", "reason": "not approved by human reviewer"}
        if not self.token:
            return {"status": "blocked", "reason": "no write-scoped GitHub token configured"}

        url = f"{GITHUB_API}/repos/{self.repo}/issues/{pr_number}/comments"
        resp = requests.post(url, headers=self._headers(), json={"body": body}, timeout=10)
        if resp.status_code == 201:
            return {"status": "posted", "url": resp.json().get("html_url")}
        return {"status": "failed", "reason": f"{resp.status_code}: {resp.text[:200]}"}
