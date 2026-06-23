"""
PR Janitor — Streamlit Dashboard

Run locally:
    streamlit run streamlit_app.py

Deploy free on Streamlit Community Cloud by connecting this repo at
https://share.streamlit.io — no server management needed.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.orchestrator import run_heuristic_pipeline

st.set_page_config(page_title="PR Janitor", page_icon="🧹", layout="wide")

CATEGORY_STYLE = {
    "spam": ("🚫", "#e74c3c"),
    "likely_duplicate": ("🔁", "#f39c12"),
    "needs_changes": ("🛠️", "#3498db"),
    "ready_to_review": ("✅", "#2ecc71"),
}

if "queue" not in st.session_state:
    st.session_state.queue = None
if "report" not in st.session_state:
    st.session_state.report = None
if "used_fallback" not in st.session_state:
    st.session_state.used_fallback = False
if "decisions" not in st.session_state:
    st.session_state.decisions = {}  # pr_number -> "approved" | "rejected"

st.title("🧹 PR Janitor")
st.caption(
    "Multi-agent PR triage built with Google ADK. Reads open PRs, flags spam/duplicates, "
    "drafts review comments — but never posts anything without your explicit approval."
)

with st.sidebar:
    st.header("Settings")
    repo = st.text_input("GitHub repo", value="freeCodeCamp/freeCodeCamp")
    limit = st.slider("Number of PRs to triage", min_value=3, max_value=20, value=7)
    run_clicked = st.button("🔍 Run Triage", type="primary", use_container_width=True)

    st.divider()
    st.markdown(
        "**Security model:** the agent that drafts comments has no GitHub "
        "write credentials. Nothing is posted until you click Approve below."
    )

if run_clicked:
    with st.spinner(f"Triaging open PRs for {repo}..."):
        result = run_heuristic_pipeline(repo, limit=limit)
    st.session_state.queue = result["approval_queue"]
    st.session_state.report = result["report"]
    st.session_state.used_fallback = result["used_fallback_data"]
    st.session_state.decisions = {}

if st.session_state.report is None:
    st.info("Set a repo in the sidebar and click **Run Triage** to get started.")
    st.stop()

if st.session_state.used_fallback:
    st.warning(
        "Live GitHub API was unavailable or rate-limited — showing bundled sample data instead. "
        "This is expected behavior, not an error: PR Janitor always degrades gracefully rather "
        "than breaking the demo."
    )
else:
    st.success("Live data from the GitHub REST API.")

# --- Summary metrics ---
report = st.session_state.report
counts = {"spam": 0, "likely_duplicate": 0, "needs_changes": 0, "ready_to_review": 0}
for row in report:
    counts[row["category"]] = counts.get(row["category"], 0) + 1

cols = st.columns(4)
labels = [("🚫 Spam", "spam"), ("🔁 Duplicates", "likely_duplicate"),
          ("🛠️ Needs Changes", "needs_changes"), ("✅ Ready to Review", "ready_to_review")]
for col, (label, key) in zip(cols, labels):
    col.metric(label, counts.get(key, 0))

st.divider()

# --- Triage report table ---
st.subheader("Triage Report")
df = pd.DataFrame(report)
df["reasoning"] = df["reasoning"].apply(lambda r: "; ".join(r) if isinstance(r, list) else r)
st.dataframe(
    df[["number", "title", "author", "category", "spam_score", "reasoning"]],
    use_container_width=True,
    hide_index=True,
)

st.divider()

# --- Approval queue ---
st.subheader("Human Approval Queue")
st.caption("Nothing below has been posted to GitHub. You decide each one.")

queue = st.session_state.queue
pending = [a for a in queue.pending()]

if not pending and not st.session_state.decisions:
    st.info("No items in the queue.")

for action in pending:
    emoji, color = CATEGORY_STYLE.get(action.category, ("•", "#888"))
    with st.container(border=True):
        st.markdown(f"**{emoji} PR #{action.pr_number}** — `{action.category}`")
        edited = st.text_area(
            "Draft comment (editable before approval)",
            value=action.draft_comment,
            key=f"draft_{action.pr_number}",
            height=80,
        )
        c1, c2, c3 = st.columns([1, 1, 4])
        if c1.button("✅ Approve", key=f"approve_{action.pr_number}"):
            if edited != action.draft_comment:
                queue.edit_and_approve(action.pr_number, edited)
            else:
                queue.approve(action.pr_number)
            st.session_state.decisions[action.pr_number] = "approved"
            st.rerun()
        if c2.button("❌ Reject", key=f"reject_{action.pr_number}"):
            queue.reject(action.pr_number)
            st.session_state.decisions[action.pr_number] = "rejected"
            st.rerun()

# --- Decision log ---
if st.session_state.decisions:
    st.divider()
    st.subheader("Decisions made this session")
    decisions_df = pd.DataFrame(
        [{"pr_number": k, "decision": v} for k, v in st.session_state.decisions.items()]
    )
    st.dataframe(decisions_df, use_container_width=True, hide_index=True)
    st.caption(
        "Note: this dashboard runs in heuristic mode with no write-scoped GitHub token "
        "configured, so 'approved' items are recorded but never actually posted — "
        "matching the safety behavior described in the architecture doc."
    )
