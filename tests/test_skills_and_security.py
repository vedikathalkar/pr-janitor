"""
Tests for PR Janitor's skills and security gate.
Run with: python -m pytest tests/ -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.security.approval_gate import ApprovalQueue, DraftAction
from src.skills import contributing_skill, duplicate_skill, spam_skill
from src.tools.github_client import GitHubClient, _extract_linked_issue, _looks_like_test_file


def test_extract_linked_issue_recognizes_closing_keywords():
    assert _extract_linked_issue("Fixes #123") == 123
    assert _extract_linked_issue("this closes: #45 finally") == 45
    assert _extract_linked_issue("Resolved #7") == 7


def test_extract_linked_issue_ignores_non_closing_references():
    assert _extract_linked_issue("see #99 for context") is None
    assert _extract_linked_issue("no issue reference here") is None


def test_looks_like_test_file_detects_common_patterns():
    assert _looks_like_test_file("src/api/handler.test.js") is True
    assert _looks_like_test_file("src/api/handler_test.py") is True
    assert _looks_like_test_file("__tests__/handler.spec.ts") is True


def test_looks_like_test_file_rejects_non_test_files():
    assert _looks_like_test_file("src/api/handler.js") is False
    assert _looks_like_test_file("README.md") is False


def test_spam_skill_flags_trivial_readme_pr():
    pr = {
        "files_changed": ["README.md"],
        "additions": 1,
        "deletions": 1,
        "linked_issue": None,
        "body": "",
        "author_total_prs_all_repos_30d": 20,
        "author_total_prs_this_repo": 1,
        "commit_messages": ["fix typo"],
    }
    result = spam_skill.evaluate(pr)
    assert result["is_likely_spam"] is True
    assert result["spam_score"] > 0.5


def test_spam_skill_does_not_flag_legit_pr():
    pr = {
        "files_changed": ["src/api/handler.js", "src/api/handler.test.js"],
        "additions": 47,
        "deletions": 12,
        "linked_issue": 123,
        "body": "Fixes a real race condition with a detailed explanation and a regression test included.",
        "author_total_prs_all_repos_30d": 5,
        "author_total_prs_this_repo": 3,
        "commit_messages": ["fix: prevent duplicate submission"],
    }
    result = spam_skill.evaluate(pr)
    assert result["is_likely_spam"] is False


def test_duplicate_skill_flags_closed_linked_issue():
    pr = {"linked_issue": 100, "title": "fix bug", "body": ""}
    closed_items = [{"number": 100, "title": "the bug", "state": "closed"}]
    result = duplicate_skill.evaluate(pr, closed_items)
    assert result["is_likely_duplicate"] is True
    assert result["matched_item"] == 100


def test_duplicate_skill_does_not_flag_open_issue_match():
    """A high-overlap match against an OPEN issue means this PR is likely
    the fix for it, not a duplicate. Regression test for a real bug found
    during development."""
    pr = {
        "linked_issue": None,
        "title": "fix: CSV export allows formula injection",
        "body": "Sanitizes leading characters before CSV export.",
    }
    closed_items = [
        {"number": 55, "title": "CSV export vulnerable to formula injection", "state": "open"}
    ]
    result = duplicate_skill.evaluate(pr, closed_items)
    assert result["is_likely_duplicate"] is False
    assert result["matched_item"] == 55


def test_quality_skill_flags_missing_tests():
    pr = {
        "files_changed": ["src/handler.js"],
        "has_tests": False,
        "body": "a fix",
        "linked_issue": None,
    }
    result = contributing_skill.evaluate(pr)
    assert result["meets_baseline"] is False
    assert any("tests" in n for n in result["notes"])


def test_quality_skill_passes_doc_only_change():
    pr = {"files_changed": ["docs/guide.md"], "has_tests": None, "body": "Updates the guide.", "linked_issue": None}
    result = contributing_skill.evaluate(pr)
    assert result["doc_only_change"] is True


def test_approval_queue_blocks_until_approved():
    queue = ApprovalQueue()
    action = DraftAction(pr_number=1, category="spam", draft_comment="hi", reasoning="test")
    queue.add(action)
    assert len(queue.pending()) == 1
    queue.approve(1)
    assert len(queue.pending()) == 0


def test_fallback_reason_distinguishes_error_types():
    client = GitHubClient(repo="x/y")
    assert "not found" in client._reason_for_status(404)
    assert "rate limit" in client._reason_for_status(403)
    assert "rate limit" in client._reason_for_status(429)
    assert "token rejected" in client._reason_for_status(401)



    client = GitHubClient(repo="some/repo", token="fake-token")
    result = client.post_comment_if_approved(1, "hi", approved=False)
    assert result["status"] == "blocked"


def test_github_client_blocks_write_without_token():
    client = GitHubClient(repo="some/repo", token=None)
    result = client.post_comment_if_approved(1, "hi", approved=True)
    assert result["status"] == "blocked"
    assert "token" in result["reason"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
