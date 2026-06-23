# PR Janitor — Architecture

## Problem

Open-source maintainers, especially during high-volume contribution events
(GSSoC, Hacktoberfest), are flooded with pull requests. A meaningful chunk
of these are low-effort "farming" PRs (typo-only README edits opened by
brand-new accounts chasing contribution badges), duplicates of already-fixed
issues, or PRs that just need a small nudge (missing tests, no linked issue)
before they're reviewable. Maintainers spend disproportionate time sorting
signal from noise instead of reviewing real contributions.

## Solution: a 4-agent triage pipeline with a human-approval boundary

```
                ┌─────────────────┐
GitHub repo ───>│  Intake Agent    │  reads open PRs + recent closed issues/PRs
                └────────┬─────────┘
                         │ normalized PR records
                ┌────────▼─────────┐
                │ Classifier Agent │  spam/farming-pattern detection (skill)
                └────────┬─────────┘
                         │ spam_score + reasons
                ┌────────▼─────────┐
                │  Triage Agent    │  duplicate detection + quality check (skills)
                └────────┬─────────┘
                         │ category: spam / likely_duplicate /
                         │           needs_changes / ready_to_review
                ┌────────▼─────────┐
                │  Drafter Agent   │  writes a comment per category
                └────────┬─────────┘
                         │ DraftAction (PENDING)
                ┌────────▼─────────┐
                │ Approval Queue   │  <-- HUMAN DECIDES HERE
                │ (security gate)  │      approve / reject / edit
                └────────┬─────────┘
                         │ only if approved + write token present
                ┌────────▼─────────┐
                │  GitHub comment  │
                └──────────────────┘
```

## Course concepts demonstrated

1. **Multi-agent system (ADK)** — four distinct `google.adk.agents.Agent`
   instances (`intake_agent`, `classifier_agent`, `triage_agent`,
   `drafter_agent`), each with a narrow responsibility and its own tools,
   composable under a root orchestrator agent via `sub_agents`.

2. **MCP-style external tool access** — `src/tools/github_client.py` wraps
   GitHub REST API reads/writes behind a single client, structured the
   same way an MCP server tool would be exposed to an agent (the project
   can be pointed at a real GitHub MCP server with no agent-logic changes,
   only swapping the tool implementation).

3. **Agent skills** — `src/skills/` contains three independently testable,
   independently loadable skill modules (`spam_skill`, `duplicate_skill`,
   `contributing_skill`). New spam patterns or quality rules can be added
   as new skill files without touching agent code.

4. **Security features** — the human-in-the-loop `ApprovalQueue`
   (`src/security/approval_gate.py`) is a structural boundary, not just a
   prompt instruction: the Drafter Agent has no access to any write
   credentials, and `GitHubClient.post_comment_if_approved()` refuses to
   act without both an explicit `approved=True` flag from a human AND a
   write-scoped token. Every decision is appended to an audit log.

## Two execution modes

- **Heuristic mode** (default): the orchestrator calls skill functions
  directly. Zero API key required, fully deterministic, used for the
  demo/judging run so it never breaks on quota or network issues.
- **LLM-orchestrated mode** (`--llm` flag): the real ADK `Agent` objects run
  through an `InMemoryRunner` with Gemini doing tool-call reasoning and
  sequencing. This is the production path; it requires `GOOGLE_API_KEY`.

Both modes terminate in the exact same `ApprovalQueue`, so the security
boundary is identical regardless of which agent runtime produced the draft.

## Resilience: live-first, mock-fallback

`GitHubClient` always attempts the live GitHub REST API first. If it's
rate-limited, unreachable, or returns an error, it transparently falls back
to bundled sample data (`src/data/sample_prs.json`) modeled on real spam vs.
legitimate PR patterns the author has observed first-hand triaging GSSoC
contributions. This was *not* a hypothetical design decision — it was hit
and exercised during development, when the sandbox's shared IP exhausted
GitHub's unauthenticated rate limit mid-build.

## What a production deployment would add

- Per-author history via a second API call (account age, total PRs across
  repos) instead of the placeholder fields left `None` in live mode
- Embedding-based duplicate detection instead of keyword overlap
- A real GitHub MCP server instead of the direct REST wrapper
- A small web dashboard for the approval queue instead of a CLI walkthrough
- Per-repo configurable thresholds (a small slow-moving repo wants more
  lenient spam thresholds than a 400k-star one)

## Live-mode accuracy notes

Two signals that were initially placeholders in live mode are now real:

- **Linked-issue detection** parses the PR body for GitHub's closing-keyword
  convention (`Fixes #N`, `Closes #N`, `Resolves #N`) — no extra API call.
- **Test-coverage detection** calls `GET /pulls/{n}/files` per PR and checks
  filenames against common test-file patterns (`.test.`, `.spec.`,
  `__tests__/`). This costs one extra API call per PR, so with an
  unauthenticated 60/hr rate limit, processing more than ~25-30 PRs in one
  run risks tripping the fallback to sample data mid-batch. Pass
  `fetch_file_details=False` to `GitHubClient.fetch_open_pull_requests()`
  (or add a `GITHUB_TOKEN` to raise the limit to 5000/hr) if you need to
  triage large batches.
