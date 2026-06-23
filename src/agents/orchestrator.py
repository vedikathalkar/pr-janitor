"""
Orchestrator

Two execution modes, both built on the SAME agents/skills/tools:

1. HEURISTIC MODE (default, no API key required)
   Calls the skill functions directly in sequence. This is what the demo
   script uses by default so judges can run it instantly with zero setup.

2. LLM-ORCHESTRATED MODE (requires GOOGLE_API_KEY)
   Uses the actual ADK Agent objects (intake_agent, classifier_agent,
   triage_agent, drafter_agent) with a Runner, letting Gemini reason
   about tool calls and sequencing. This is the "real" multi-agent path
   described in the architecture doc and is what we'd run in production.

Both modes produce the same DraftAction objects in the ApprovalQueue —
the human-in-the-loop boundary is identical either way.
"""

import os
from typing import Any

from src.security.approval_gate import ApprovalQueue, DraftAction
from src.skills import contributing_skill, duplicate_skill, spam_skill
from src.tools.github_client import GitHubClient

TEMPLATES = {
    "spam": (
        "Hi @{author}, thanks for opening this PR! This change looks quite small and isn't "
        "linked to an open issue, so it's been flagged for maintainer review before further "
        "action. If this addresses a real problem, could you add a short description and link "
        "the relevant issue?"
    ),
    "likely_duplicate": (
        "Hi @{author}, thanks for the contribution! This looks like it may already be covered "
        "({ref}). Could you confirm whether this is still needed, or close it if already handled?"
    ),
    "needs_changes": (
        "Hi @{author}, thanks for the PR! Before this can be reviewed, could you address: "
        "{notes}. Happy to take another look once updated."
    ),
    "ready_to_review": (
        "Hi @{author}, this PR passes our automated triage checks (tests present, issue linked, "
        "no duplicate detected) and is ready for maintainer review."
    ),
}


def _draft_comment(pr: dict[str, Any], category: str, reasoning: list[str]) -> str:
    notes_str = "; ".join(reasoning) if reasoning else "see triage notes"
    template = TEMPLATES.get(category, TEMPLATES["needs_changes"])
    return template.format(author=pr.get("author", "contributor"), notes=notes_str, ref=notes_str)


def run_heuristic_pipeline(repo: str, limit: int = 10, audit_log_path: str | None = None) -> dict[str, Any]:
    """
    Runs Intake -> Classifier -> Triage -> Drafter using the skill functions
    directly (no LLM call). Returns a full report plus a populated
    ApprovalQueue. This is the default, zero-setup demo path.
    """
    client = GitHubClient(repo=repo)
    prs = client.fetch_open_pull_requests(limit=limit)
    closed_items = client.fetch_closed_issues_and_prs()
    used_fallback = client.used_fallback

    queue = ApprovalQueue(audit_log_path=audit_log_path)
    report_rows = []

    for pr in prs:
        spam_result = spam_skill.evaluate(pr)

        if spam_result["is_likely_spam"]:
            category, reasoning = "spam", spam_result["reasons"]
        else:
            dup_result = duplicate_skill.evaluate(pr, closed_items)
            if dup_result["is_likely_duplicate"]:
                category, reasoning = "likely_duplicate", [dup_result["reason"]]
            else:
                quality_result = contributing_skill.evaluate(pr)
                if not quality_result["meets_baseline"]:
                    category, reasoning = "needs_changes", quality_result["notes"]
                else:
                    category, reasoning = "ready_to_review", ["passes spam, duplicate, and quality checks"]

        comment = _draft_comment(pr, category, reasoning)
        queue.add(DraftAction(
            pr_number=pr["number"],
            category=category,
            draft_comment=comment,
            reasoning="; ".join(reasoning),
        ))

        report_rows.append({
            "number": pr["number"],
            "title": pr["title"],
            "author": pr["author"],
            "category": category,
            "reasoning": reasoning,
            "spam_score": spam_result["spam_score"],
        })

    return {
        "repo": repo,
        "used_fallback_data": used_fallback,
        "report": report_rows,
        "approval_queue": queue,
    }


def run_llm_orchestrated_pipeline(repo: str, limit: int = 10) -> str:
    """
    Production path: runs the real ADK Agent objects through a Runner with
    Gemini doing the reasoning/sequencing. Requires GOOGLE_API_KEY.
    Returns the final text response from the orchestrating agent.
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        raise RuntimeError(
            "GOOGLE_API_KEY not set. LLM-orchestrated mode requires a Gemini API key. "
            "Use run_heuristic_pipeline() for a key-free demo."
        )

    from google.adk.agents import Agent
    from google.adk.runners import InMemoryRunner

    from src.agents.classifier_agent import classifier_agent
    from src.agents.drafter_agent import drafter_agent
    from src.agents.intake_agent import intake_agent
    from src.agents.triage_agent import triage_agent

    pr_janitor_root = Agent(
        name="pr_janitor_orchestrator",
        model="gemini-2.0-flash",
        description="Coordinates Intake, Classifier, Triage, and Drafter sub-agents to triage open PRs.",
        instruction=(
            f"Process open PRs for repo '{repo}' (limit {limit}). Delegate to "
            "intake_agent first, then classifier_agent, then triage_agent, then "
            "drafter_agent in that order. Summarize the final triage report."
        ),
        sub_agents=[intake_agent, classifier_agent, triage_agent, drafter_agent],
    )

    runner = InMemoryRunner(agent=pr_janitor_root)
    result = runner.run(user_id="demo_user", message=f"Triage open PRs for {repo}")
    return str(result)
