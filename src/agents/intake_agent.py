"""
Intake Agent

Responsibility: pull raw PR + repo context data and hand it downstream
in normalized form. This is the only agent that talks to GitHub for reads.
"""

from typing import Any

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from src.tools.github_client import GitHubClient


def fetch_open_prs(repo: str, limit: int = 10) -> dict[str, Any]:
    """Fetch up to `limit` open pull requests for `repo` (e.g. 'freeCodeCamp/freeCodeCamp').

    Returns normalized PR records plus a flag indicating whether bundled
    sample data was used (e.g. because the live GitHub API was rate-limited).
    """
    client = GitHubClient(repo=repo)
    prs = client.fetch_open_pull_requests(limit=limit)
    return {"repo": repo, "pull_requests": prs, "used_fallback_data": client.used_fallback}


def fetch_closed_context(repo: str) -> dict[str, Any]:
    """Fetch recently closed issues/PRs for `repo`, used later for duplicate detection."""
    client = GitHubClient(repo=repo)
    items = client.fetch_closed_issues_and_prs()
    return {"repo": repo, "closed_items": items, "used_fallback_data": client.used_fallback}


intake_agent = Agent(
    name="intake_agent",
    model="gemini-2.0-flash",
    description="Pulls open PRs and recent closed-issue context from a GitHub repo.",
    instruction=(
        "You are the Intake Agent for PR Janitor. Your only job is to call "
        "fetch_open_prs and fetch_closed_context for the repo you're given, "
        "and pass the raw results downstream. Do not analyze or judge the PRs "
        "yourself — that is the Classifier and Triage agents' job."
    ),
    tools=[FunctionTool(fetch_open_prs), FunctionTool(fetch_closed_context)],
)
