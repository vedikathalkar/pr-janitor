"""
Classifier Agent

Responsibility: run the spam_detection skill against each PR and produce
an explainable score + reasons. Designed so new skills (additional spam
patterns) can be dropped into src/skills/ and registered here without
touching any other agent.
"""

from typing import Any

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from src.skills import spam_skill


def classify_pr_spam_risk(pr: dict[str, Any]) -> dict[str, Any]:
    """Run the spam-detection skill against a single normalized PR record.

    Returns a spam_score (0-1), a boolean is_likely_spam, and a list of
    human-readable reasons supporting the score.
    """
    return spam_skill.evaluate(pr)


classifier_agent = Agent(
    name="classifier_agent",
    model="gemini-2.0-flash",
    description="Scores each PR for spam/low-effort-farming likelihood with explainable reasons.",
    instruction=(
        "You are the Classifier Agent for PR Janitor. For each PR you receive, "
        "call classify_pr_spam_risk and report the score and reasons plainly. "
        "Never mark a PR as spam with high confidence unless the tool's reasons "
        "clearly support it — when uncertain, say so and let the Triage Agent decide."
    ),
    tools=[FunctionTool(classify_pr_spam_risk)],
)
