"""
Skill: quality_check

Checks whether a PR follows baseline contribution hygiene:
- includes tests when it touches non-trivial source files
- has a non-empty, substantive description
- has a linked issue (repo convention for most large OSS projects)

This skill is deliberately lenient — it informs the triage category,
it never blocks or flags a PR as spam on its own.
"""

from typing import Any

DOC_ONLY_EXTENSIONS = {".md", ".txt"}


def _is_doc_only(files: list[str]) -> bool:
    if not files:
        return False
    return all(any(f.endswith(ext) for ext in DOC_ONLY_EXTENSIONS) for f in files)


def evaluate(pr: dict[str, Any]) -> dict[str, Any]:
    files = pr.get("files_changed") or []
    notes: list[str] = []

    doc_only = _is_doc_only(files)
    has_tests = pr.get("has_tests")
    body = (pr.get("body") or "").strip()

    if not doc_only and has_tests is False:
        notes.append("touches source files but includes no tests")
    if not doc_only and has_tests is None:
        notes.append("test coverage unknown (live PR — file-level diff not fetched)")

    if len(body) < 20:
        notes.append("PR description is missing or very thin")

    if not pr.get("linked_issue") and not doc_only:
        notes.append("no linked issue for a non-trivial code change")

    meets_baseline = not notes
    return {
        "skill": "quality_check",
        "meets_baseline": meets_baseline,
        "notes": notes,
        "doc_only_change": doc_only,
    }
