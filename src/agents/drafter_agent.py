"""
Drafter Agent

Responsibility: write a polite, specific review comment per triage
category, and push it into the ApprovalQueue. This agent NEVER has
access to a write-scoped GitHub token or the post_comment_if_approved
method — that boundary is enforced structurally, not just by instruction,
so a prompt-injected or misbehaving agent still cannot post on its own.
"""

from typing import Any

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from src.security.approval_gate import ApprovalQueue, DraftAction

TEMPLATES = {
    "spam": (
        "Hi @{author}, thanks for opening this PR! This change looks quite small and isn't "
        "linked to an open issue, so it's been flagged for maintainer review before further "
        "action. If this addresses a real problem, could you add a short description and link "
        "the relevant issue?"
    ),
    "likely_duplicate": (
        "Hi @{author}, thanks for the contribution! This looks like it may overlap with "
        "{matched_ref}. Could you confirm whether this is still needed, or close it if already covered?"
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


def draft_comment(pr_number: int, author: str, category: str, reasoning: list[str]) -> dict[str, Any]:
    """Generate a draft review comment for a PR given its triage category and reasoning.

    Does NOT post anything. Returns the draft text and reasoning for a human
    to review via the approval queue.
    """
    template = TEMPLATES.get(category, TEMPLATES["needs_changes"])
    notes_str = "; ".join(reasoning) if reasoning else "see triage notes"
    matched_ref = f"item referenced in: {notes_str}"
    comment = template.format(author=author, notes=notes_str, matched_ref=matched_ref)
    return {
        "pr_number": pr_number,
        "category": category,
        "draft_comment": comment,
        "reasoning": notes_str,
    }


def queue_for_approval(pr_number: int, category: str, draft_comment_text: str, reasoning: str, queue: ApprovalQueue) -> dict[str, Any]:
    """Push a drafted comment into the human approval queue. This is a NO-OP write —
    nothing is posted to GitHub until a maintainer explicitly approves it."""
    action = DraftAction(
        pr_number=pr_number,
        category=category,
        draft_comment=draft_comment_text,
        reasoning=reasoning,
    )
    queue.add(action)
    return {"status": "queued_for_human_approval", "pr_number": pr_number}


drafter_agent = Agent(
    name="drafter_agent",
    model="gemini-2.0-flash",
    description="Writes draft review comments per triage category and queues them for human approval. Never posts directly.",
    instruction=(
        "You are the Drafter Agent for PR Janitor. For each triaged PR, call "
        "draft_comment to produce a polite, specific comment, then call "
        "queue_for_approval to place it in the human review queue. You have no "
        "ability to post comments to GitHub directly — that requires explicit "
        "human approval through a separate, privileged step."
    ),
    tools=[FunctionTool(draft_comment)],  # queue_for_approval bound at runtime with a live queue instance
)
