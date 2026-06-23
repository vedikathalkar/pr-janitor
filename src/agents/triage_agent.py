"""
Triage Agent

Responsibility: for PRs that pass the spam filter, determine the
final category a maintainer cares about:
  - ready_to_review
  - needs_changes (missing tests / thin description / no linked issue)
  - likely_duplicate
  - spam (passthrough from Classifier, for completeness in the report)
"""

from typing import Any

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from src.skills import contributing_skill, duplicate_skill


def check_duplicate(pr: dict[str, Any], closed_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Check whether a PR is likely a duplicate of a closed issue/PR."""
    return duplicate_skill.evaluate(pr, closed_items)


def check_quality(pr: dict[str, Any]) -> dict[str, Any]:
    """Check a PR against baseline contribution hygiene (tests, description, linked issue)."""
    return contributing_skill.evaluate(pr)


def assign_category(spam_result: dict[str, Any], duplicate_result: dict[str, Any], quality_result: dict[str, Any]) -> dict[str, Any]:
    """Combine skill outputs into a single triage category with reasoning."""
    if spam_result.get("is_likely_spam"):
        return {"category": "spam", "reasoning": spam_result.get("reasons", [])}
    if duplicate_result.get("is_likely_duplicate"):
        return {"category": "likely_duplicate", "reasoning": [duplicate_result.get("reason")]}
    if not quality_result.get("meets_baseline", True):
        return {"category": "needs_changes", "reasoning": quality_result.get("notes", [])}
    return {"category": "ready_to_review", "reasoning": ["passes spam, duplicate, and quality checks"]}


triage_agent = Agent(
    name="triage_agent",
    model="gemini-2.0-flash",
    description="Assigns each non-spam PR a final triage category: ready_to_review, needs_changes, or likely_duplicate.",
    instruction=(
        "You are the Triage Agent for PR Janitor. For each PR, call check_duplicate "
        "and check_quality, then call assign_category with the classifier's spam "
        "result plus your two results to get the final category. Report category "
        "and reasoning clearly so the Drafter Agent can write an appropriate comment."
    ),
    tools=[FunctionTool(check_duplicate), FunctionTool(check_quality), FunctionTool(assign_category)],
)
