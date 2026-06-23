# PR Janitor: Autonomous PR Triage with a Human-in-the-Loop Safety Gate

**Track:** Agents for Business
**Course:** Kaggle 5-Day AI Agents: Intensive Vibe Coding Course with Google (June 2026)

---

## The Problem

Open-source maintainers are drowning in pull requests they didn't ask for.
During contribution events like GSSoC and Hacktoberfest, a meaningful chunk
of incoming PRs are low-effort "farming" submissions — typo-only README
edits from brand-new accounts chasing a contribution badge — mixed in with
genuine duplicates of already-fixed issues and PRs that just need one small
nudge (a missing test, no linked issue) before they're reviewable.

I didn't invent this problem — I lived it. While contributing to multiple
GSSoC '26 repositories this season, I personally triaged dozens of PRs by
hand: filtering spam, catching duplicates, and flagging missing tests. PR
Janitor automates that first pass so maintainers spend their limited review
time on the PRs that actually deserve a human look.

## The Solution

PR Janitor is a 4-agent pipeline, built with Google's Agent Development Kit
(ADK), that reads open PRs from a GitHub repo, scores them for spam/farming
patterns, checks for duplicates and baseline quality, and drafts a specific
review comment — **but never posts anything without explicit human
approval.** The approval boundary is structural: the agent that writes
comments has no GitHub write credentials at all.

```
GitHub repo ──> Intake Agent ──> Classifier Agent ──> Triage Agent ──> Drafter Agent ──> Approval Queue ──[human decides]──> GitHub comment
                (reads PRs)      (spam scoring)        (duplicate +      (writes draft,
                                                         quality check)    cannot post)
```

## Course Concepts Demonstrated

**1. Multi-agent system (ADK)**
Four distinct `google.adk.agents.Agent` instances, each with a narrow
responsibility and its own tools, composed under a root orchestrator via
`sub_agents`:
- `intake_agent` — reads open PRs and recent closed-issue context
- `classifier_agent` — scores spam/farming likelihood with explainable reasons
- `triage_agent` — checks duplicates and contribution-hygiene quality
- `drafter_agent` — writes a category-specific comment, queues it for approval

**2. Tool / external-service integration (MCP-style)**
`GitHubClient` wraps GitHub's REST API behind a single tool interface,
structured the same way an MCP server tool would be exposed to an agent —
the architecture can be pointed at a real GitHub MCP server with zero
changes to agent logic, only swapping the tool implementation underneath.

**3. Agent skills**
Three independently testable, independently loadable skill modules live in
`src/skills/`: `spam_skill`, `duplicate_skill`, `contributing_skill`. New
spam patterns or quality rules can be dropped in as new skill files without
touching any agent code — this is what let me fix a real bug (see
Evaluation below) by editing one skill in isolation.

**4. Security features**
This is the project's central design decision, not an afterthought:
- The `ApprovalQueue` (`src/security/approval_gate.py`) is a structural
  boundary — the Drafter Agent has no write-scoped GitHub token and cannot
  post under any circumstance.
- `GitHubClient.post_comment_if_approved()` refuses to act unless **both**
  an explicit human `approved=True` flag **and** a write-scoped token are
  present — absence of either is a no-op, never a silent failure.
- Every approve/reject decision is written to an audit log (who/when/what),
  important for any team that wants a paper trail on autonomous agent
  actions in their repo.

## Implementation Details

- **Language/framework:** Python, Google ADK 2.3
- **Two execution modes, same output:**
  - *Heuristic mode* (default) — the orchestrator calls skill functions
    directly. Zero API key required, fully deterministic — used for the
    demo so it never breaks on quota or network issues.
  - *LLM-orchestrated mode* (`--llm` flag) — the real ADK `Agent` objects
    run through an `InMemoryRunner` with Gemini handling tool-call
    reasoning and sequencing. This is the production path.
  - Both modes terminate in the exact same `ApprovalQueue` — the security
    boundary doesn't change based on which runtime produced the draft.
- **Resilience:** `GitHubClient` always tries the live GitHub REST API
  first and transparently falls back to a bundled sample dataset if the
  call is rate-limited or fails. This wasn't a hypothetical design
  decision — it was exercised mid-development when a shared sandbox IP
  hit GitHub's unauthenticated rate limit.
- **Linked-issue detection** parses PR bodies for GitHub's closing-keyword
  convention (`Fixes #N`, `Closes #N`, `Resolves #N`) — no extra API call.
- **Test-coverage detection** fetches each PR's changed-file list and
  checks filenames against common test patterns, with graceful per-PR
  degradation if that call fails.

## Evaluation

13 automated tests cover every skill, the security gate, and the GitHub
client's blocking behavior. One test is a direct record of a real bug
caught during development: a duplicate-detection rule was initially
flagging a *legitimate security fix* as a duplicate, because it matched
keywords against a closed item without checking whether that item was
actually closed (versus still open and waiting on exactly that fix). Once
caught, this is now a permanent regression test — `test_duplicate_skill_does_not_flag_open_issue_match`.

Run live against `freeCodeCamp/freeCodeCamp`, the system correctly:
- Flagged trivial README-only PRs from new accounts as spam
- Identified a PR whose title closely matched an already-closed PR as a likely duplicate
- Correctly passed a well-tested, properly-linked security fix as `ready_to_review`

## Value

For a maintainer, this turns "scroll through 30 unsorted PRs" into "review
6 pre-sorted, pre-explained items, approve or edit 6 draft comments." No
PR is ever silently auto-closed or auto-commented — the system surfaces
judgment, it doesn't replace it.

## Limitations & Next Steps

- Duplicate detection uses keyword overlap, not embeddings — a documented,
  intentional simplification for a 2-week build
- Author-history signals (account age, cross-repo PR velocity) require a
  second API call per author not yet implemented in live mode
- A web dashboard would replace the current CLI approval walkthrough for
  a more realistic maintainer workflow

## Links

- **Code:** [GitHub repo link here]
- **Video demo:** [YouTube/Loom link here]
- **Live project:** [if deployed, link here]
