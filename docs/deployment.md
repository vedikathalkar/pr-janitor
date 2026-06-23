# Deploying PR Janitor — Step by Step

## 1. Push to GitHub (do this on your machine, in Command Prompt)

```bat
cd path\to\pr-janitor
git init
git add .
git commit -m "Initial commit: PR Janitor multi-agent PR triage system"
```

Create a new **public** repo on GitHub first (via github.com → New repository,
name it `pr-janitor`, do NOT initialize with a README since you already have one).

Then connect and push:

```bat
git remote add origin https://github.com/vedikathalkar/pr-janitor.git
git branch -M main
git push -u origin main
```

If prompted for credentials, use a Personal Access Token (not your password) —
GitHub no longer accepts password auth for git operations.

## 2. Deploy the dashboard on Streamlit Community Cloud (free)

1. Go to https://share.streamlit.io and sign in with your GitHub account
   (the same `vedikathalkar` account).
2. Click **"New app"**.
3. Choose:
   - Repository: `vedikathalkar/pr-janitor`
   - Branch: `main`
   - Main file path: `streamlit_app.py`
4. Click **Deploy**.

That's it — Streamlit Cloud installs `requirements.txt` automatically and
gives you a public URL like:

```
https://pr-janitor-vedikathalkar.streamlit.app
```

This URL is what goes in your Kaggle writeup's "Live project" link.

## 3. (Optional) Raise the GitHub rate limit for the live demo

By default the app makes unauthenticated GitHub API calls (60 requests/hour
shared across anyone using the deployed app). To avoid hitting that limit
during judging:

1. Create a GitHub Personal Access Token with **no scopes selected**
   (read-only public data needs none) at
   https://github.com/settings/tokens
2. In your Streamlit Cloud app dashboard, go to **Settings → Secrets** and add:
   ```toml
   GITHUB_TOKEN = "your_token_here"
   ```
3. Reboot the app from the Streamlit Cloud dashboard.

This raises the limit from 60/hr to 5,000/hr — plenty for judges clicking
around during review.

## 4. Verify it works

Open the deployed URL, click **Run Triage** with the default repo, and
confirm you see the metrics, the triage table, and the approval queue with
working Approve/Reject buttons.
