# PR Janitor 🧹

A multi-agent system that triages open-source pull requests: flags
low-effort "farming" PRs, catches duplicates of already-fixed issues,
checks baseline contribution hygiene (tests, description, linked issue),
and drafts a maintainer-ready review comment — **never posting anything
without explicit human approval.**

Built for the Kaggle **AI Agents: Intensive Vibe Coding Capstone Project**
(Agents for Business track).

## Why this exists

During GSSoC '26, I personally triaged dozens of real PRs across multiple
repos and saw the same patterns over and over: typo-only README PRs from
brand-new accounts farming contribution counts, duplicate fixes for
already-closed issues, and PRs missing tests or a linked issue. PR Janitor
automates the first pass of that triage so maintainers spend their time on
PRs that actually need a human.

## Dashboard (recommended way to demo this)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens a browser dashboard: set a repo in the sidebar, click **Run triage**,
see the color-coded report, then approve/reject/edit each draft comment in
the **Human Approval Queue** tab. Nothing is ever posted to GitHub from
here — it's a safe, visual way to walk through the same pipeline as the
CLI demo below.

### Deploy it live, for free

1. Push this repo to GitHub (public).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, click **New app**, and point it at this repo + `app.py`.
3. (Optional) In the app's **Settings → Secrets**, add:
   ```
   GITHUB_TOKEN = "ghp_..."
   ```
   to raise the GitHub API rate limit from 60/hr to 5000/hr. Not required —
   the dashboard works fine without it, falling back to sample data if
   rate-limited.
4. Done — you get a public `*.streamlit.app` URL to put in your Kaggle writeup.

## CLI demo (no API key needed)

```bash
pip install -r requirements.txt
python demo/run_demo.py
```

That's it — runs against `freeCodeCamp/freeCodeCamp` in heuristic mode,
using live GitHub data if available or bundled sample data if the API is
rate-limited (very likely on a shared IP without a token).

### Walk through the human-approval queue

```bash
python demo/run_demo.py --interactive --audit-log audit.jsonl
```

You'll see each draft comment and choose approve / reject / skip for each
one. Nothing is ever posted to GitHub in this mode — there's no write
token configured by default.

### Run against a different repo

```bash
python demo/run_demo.py --repo your-org/your-repo --limit 15
```

### Run the real ADK + Gemini multi-agent pipeline

```bash
export GOOGLE_API_KEY=your-key-here
python demo/run_demo.py --llm
```

## Project structure

```
src/
  agents/        4 ADK agents: intake, classifier, triage, drafter
  skills/        spam_detection, duplicate_detection, quality_check
  tools/         github_client.py (live API + sample-data fallback)
  security/      approval_gate.py — the human-in-the-loop boundary
  data/          sample_prs.json — fallback dataset, modeled on real patterns
demo/
  run_demo.py    CLI entry point
docs/
  architecture.md
```

See `docs/architecture.md` for the full pipeline diagram and a mapping of
which course concepts (multi-agent systems, MCP-style tools, agent skills,
security features) are demonstrated where.

## Security model, in one sentence

The system can read and reason autonomously; it can never write (post a
comment) without an explicit per-item human approval, and the agent that
drafts comments has no write credentials at all — the boundary is
structural, not just instructional.
