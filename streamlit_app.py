"""
PR Janitor — Streamlit Dashboard

Run locally:
    streamlit run app.py

Deploy for free:
    Push this repo to GitHub, then connect it at https://share.streamlit.io
    (Streamlit Community Cloud). No paid services required — runs in
    heuristic mode (no LLM API key needed) by default.

Optional secrets (Settings -> Secrets on Streamlit Cloud, or .streamlit/secrets.toml locally):
    GITHUB_TOKEN = "ghp_..."   # raises GitHub API rate limit from 60/hr to 5000/hr
"""

import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src.agents.orchestrator import run_heuristic_pipeline
from src.security.approval_gate import ActionStatus

st.set_page_config(page_title="PR Janitor", page_icon="🧹", layout="wide")

# ---- minimal custom styling ----
st.markdown(
    """
    <style>
    .stApp { background-color: #0e1117; }
    .pj-card {
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
        border-left: 4px solid #444;
    }
    .pj-spam { border-left-color: #e25555; background-color: rgba(226,85,85,0.08); }
    .pj-dup { border-left-color: #e2a855; background-color: rgba(226,168,85,0.08); }
    .pj-needs { border-left-color: #e2cf55; background-color: rgba(226,207,85,0.08); }
    .pj-ready { border-left-color: #55c97a; background-color: rgba(85,201,122,0.08); }
    .pj-title { font-size: 1.0rem; font-weight: 600; margin-bottom: 2px; }
    .pj-meta { font-size: 0.82rem; opacity: 0.7; margin-bottom: 6px; }
    .pj-reason { font-size: 0.85rem; opacity: 0.85; }
    </style>
    """,
    unsafe_allow_html=True,
)

CATEGORY_STYLE = {
    "spam": ("🚫", "pj-spam", "Spam / low-effort"),
    "likely_duplicate": ("🔁", "pj-dup", "Likely duplicate"),
    "needs_changes": ("🛠️", "pj-needs", "Needs changes"),
    "ready_to_review": ("✅", "pj-ready", "Ready to review"),
}

# ---- sidebar controls ----
with st.sidebar:
    st.title("🧹 PR Janitor")
    st.caption("Multi-agent PR triage with a human-approval gate")
    repo = st.text_input("Repository", value="freeCodeCamp/freeCodeCamp")
    limit = st.slider("Max PRs to fetch", min_value=3, max_value=20, value=7)
    fetch_files = st.checkbox("Fetch real test-coverage data (1 extra API call/PR)", value=True)
    run_clicked = st.button("Run triage", type="primary", use_container_width=True)
    st.divider()
    st.caption(
        "Runs in heuristic mode — no LLM API key required. "
        "Nothing is ever posted to GitHub from this dashboard; "
        "approvals here are recorded locally only."
    )

if "result" not in st.session_state:
    st.session_state.result = None

if run_clicked:
    token = st.secrets.get("GITHUB_TOKEN", None) if hasattr(st, "secrets") else None
    os.environ.setdefault("GITHUB_TOKEN", token or "")
    with st.spinner("Running Intake → Classifier → Triage → Drafter..."):
        st.session_state.result = run_heuristic_pipeline(repo, limit=limit)

result = st.session_state.result

st.header("PR Janitor")
st.caption("Reads, scores, and drafts — never posts without your approval.")

if result is None:
    st.info("Set a repo in the sidebar and click **Run triage** to get started.")
else:
    if result["used_fallback_data"]:
        st.warning(
            "Live GitHub API unavailable or rate-limited — showing bundled sample data "
            "modeled on real spam vs. legitimate PR patterns.",
            icon="⚠️",
        )
    else:
        st.success(f"Live data pulled from {result['repo']}", icon="✅")

    counts = {}
    for row in result["report"]:
        counts[row["category"]] = counts.get(row["category"], 0) + 1

    cols = st.columns(4)
    for col, cat in zip(cols, ["spam", "likely_duplicate", "needs_changes", "ready_to_review"]):
        emoji, _, label = CATEGORY_STYLE[cat]
        col.metric(f"{emoji} {label}", counts.get(cat, 0))

    st.divider()

    tab_report, tab_queue = st.tabs(["📋 Triage Report", "✅ Human Approval Queue"])

    with tab_report:
        for row in result["report"]:
            emoji, css_class, label = CATEGORY_STYLE.get(row["category"], ("•", "", row["category"]))
            reasons_html = "".join(f"<div class='pj-reason'>• {r}</div>" for r in row["reasoning"])
            st.markdown(
                f"""
                <div class="pj-card {css_class}">
                    <div class="pj-title">{emoji} PR #{row['number']} — {row['title']}</div>
                    <div class="pj-meta">by @{row['author']} · {label} · spam score {row['spam_score']}</div>
                    {reasons_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tab_queue:
        queue = result["approval_queue"]
        pending = queue.pending()

        if not pending:
            st.success("No items pending approval.")
        else:
            st.caption(f"{len(pending)} draft comments awaiting your decision. Nothing below has been posted anywhere.")
            for action in pending:
                emoji, css_class, label = CATEGORY_STYLE.get(action.category, ("•", "", action.category))
                with st.container():
                    st.markdown(
                        f"<div class='pj-card {css_class}'><div class='pj-title'>{emoji} PR #{action.pr_number} · {label}</div></div>",
                        unsafe_allow_html=True,
                    )
                    edited = st.text_area(
                        "Draft comment", value=action.draft_comment, key=f"text_{action.pr_number}", height=90
                    )
                    c1, c2, c3 = st.columns([1, 1, 4])
                    if c1.button("✅ Approve", key=f"approve_{action.pr_number}"):
                        if edited != action.draft_comment:
                            queue.edit_and_approve(action.pr_number, edited)
                        else:
                            queue.approve(action.pr_number)
                        st.rerun()
                    if c2.button("❌ Reject", key=f"reject_{action.pr_number}"):
                        queue.reject(action.pr_number)
                        st.rerun()
                    st.divider()

        decided = [a for a in queue._items.values() if a.status != ActionStatus.PENDING]
        if decided:
            with st.expander(f"Decision history ({len(decided)})"):
                for action in decided:
                    icon = "✅" if "approved" in action.status.value else "❌"
                    st.write(f"{icon} PR #{action.pr_number} — {action.status.value} at {action.decided_at}")

st.divider()
st.caption(
    "PR Janitor · built for the Kaggle AI Agents Capstone Project · "
    "Agents for Business track · runs on Google ADK"
)
