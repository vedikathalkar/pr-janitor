"""
PR Janitor — Demo Runner

Usage:
    python demo/run_demo.py
    python demo/run_demo.py --repo freeCodeCamp/freeCodeCamp --limit 7
    python demo/run_demo.py --interactive   # walk through approval queue manually

By default runs in heuristic mode (no API key needed). Pass --llm to use
the real ADK + Gemini orchestration path (requires GOOGLE_API_KEY).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.orchestrator import run_heuristic_pipeline, run_llm_orchestrated_pipeline

CATEGORY_EMOJI = {
    "spam": "🚫",
    "likely_duplicate": "🔁",
    "needs_changes": "🛠️",
    "ready_to_review": "✅",
}


def print_report(result: dict) -> None:
    print(f"\n=== PR Janitor Report: {result['repo']} ===")
    if result["used_fallback_data"]:
        reason = result.get("fallback_reason") or "live GitHub API unavailable"
        print(f"(Using bundled sample data — reason: {reason})\n")
    else:
        print("(Live data from GitHub REST API)\n")

    for row in result["report"]:
        emoji = CATEGORY_EMOJI.get(row["category"], "•")
        print(f"{emoji} PR #{row['number']} — {row['title']!r} by @{row['author']}")
        print(f"   category: {row['category']} (spam_score={row['spam_score']})")
        for r in row["reasoning"]:
            print(f"   - {r}")
        print()


def run_approval_walkthrough(queue) -> None:
    pending = queue.pending()
    if not pending:
        print("No pending items in the approval queue.")
        return

    print(f"\n=== Human Approval Queue ({len(pending)} pending) ===")
    print("Nothing below has been posted to GitHub. You decide each one.\n")

    for action in pending:
        print(f"--- PR #{action.pr_number} [{action.category}] ---")
        print(f"Draft comment:\n  {action.draft_comment}\n")
        choice = input("Approve (a) / Reject (r) / Skip (s): ").strip().lower()
        if choice == "a":
            queue.approve(action.pr_number)
            print("-> approved (would be posted with a write-scoped token configured)\n")
        elif choice == "r":
            queue.reject(action.pr_number)
            print("-> rejected\n")
        else:
            print("-> skipped (still pending)\n")


def main():
    parser = argparse.ArgumentParser(description="PR Janitor demo")
    parser.add_argument("--repo", default="freeCodeCamp/freeCodeCamp")
    parser.add_argument("--limit", type=int, default=7)
    parser.add_argument("--llm", action="store_true", help="Use real ADK+Gemini orchestration (needs GOOGLE_API_KEY)")
    parser.add_argument("--interactive", action="store_true", help="Walk through the approval queue interactively")
    parser.add_argument("--audit-log", default=None, help="Path to write an audit log of approval decisions")
    args = parser.parse_args()

    if args.llm:
        print(run_llm_orchestrated_pipeline(args.repo, args.limit))
        return

    result = run_heuristic_pipeline(args.repo, args.limit, audit_log_path=args.audit_log)
    print_report(result)

    if args.interactive:
        run_approval_walkthrough(result["approval_queue"])
    else:
        pending = result["approval_queue"].pending()
        print(f"{len(pending)} draft comments queued for human approval. "
              f"Run with --interactive to approve/reject them.")


if __name__ == "__main__":
    main()
