"""
Streamlit dashboard over results/eval.db.

Everything here is a thin read layer on top of the tables src/load_db.py
builds — no logic lives here that isn't already in src/scoring.py or the
queries/*.sql files; the dashboard exists to make those numbers explorable
without writing SQL by hand each time.

Usage:
    streamlit run dashboard/app.py
"""

import sqlite3
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "results" / "eval.db"

st.set_page_config(page_title="Self-Harm Eval Dashboard", layout="wide")
st.title("Self-Harm Risk Evaluation — Dashboard")
st.caption(
    "Read-only view over results/eval.db. Run `python src/classify.py`, "
    "`python src/load_db.py`, and optionally `python src/qa_review.py` to populate it."
)

if not DB_PATH.exists():
    st.warning(
        "No results/eval.db found yet. From the project root, run:\n\n"
        "```bash\n"
        "python src/classify.py\n"
        "python src/load_db.py\n"
        "```"
    )
    st.stop()

conn = sqlite3.connect(DB_PATH)

runs = pd.read_sql("SELECT run_id, model FROM runs ORDER BY run_id DESC", conn)
if runs.empty:
    st.warning(
        "results/eval.db exists but has no runs yet. Run src/classify.py, then src/load_db.py."
    )
    st.stop()

selected_run = st.selectbox("Run", runs["run_id"], index=0)
model_for_run = runs.loc[runs["run_id"] == selected_run, "model"].iloc[0]
st.caption(f"Model: `{model_for_run}`")

joined = pd.read_sql(
    """
    SELECT ec.id, ec.text, ec.gold_tier, ec.edge_case_type, ec.ambiguous,
           p.predicted_tier, p.rationale
    FROM eval_cases ec
    JOIN predictions p ON p.case_id = ec.id
    WHERE p.run_id = ? AND p.predicted_tier IS NOT NULL
    """,
    conn,
    params=(selected_run,),
)

col1, col2, col3, col4 = st.columns(4)
n = len(joined)
accuracy = (joined["gold_tier"] == joined["predicted_tier"]).mean() if n else float("nan")
critical_misses = joined[(joined["gold_tier"] == 3) & (joined["predicted_tier"] < 3)]
tier3_total = (joined["gold_tier"] == 3).sum()
tier3_recall = (
    1 - len(critical_misses) / tier3_total if tier3_total else float("nan")
)

col1.metric("Cases scored", n)
col2.metric("Overall accuracy", f"{accuracy:.0%}" if n else "—")
col3.metric("Tier-3 recall", f"{tier3_recall:.0%}" if tier3_total else "—")
col4.metric("Critical misses", len(critical_misses), delta_color="inverse")

if len(critical_misses):
    st.error(
        f"{len(critical_misses)} critical miss(es) — imminent-risk cases scored below tier 3."
    )
    st.dataframe(
        critical_misses[["id", "text", "gold_tier", "predicted_tier", "rationale"]],
        hide_index=True,
    )

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Per-tier precision / recall")
    rows = []
    for tier in (0, 1, 2, 3):
        tp = ((joined["gold_tier"] == tier) & (joined["predicted_tier"] == tier)).sum()
        fp = ((joined["gold_tier"] != tier) & (joined["predicted_tier"] == tier)).sum()
        fn = ((joined["gold_tier"] == tier) & (joined["predicted_tier"] != tier)).sum()
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        rows.append({"tier": tier, "metric": "precision", "value": precision})
        rows.append({"tier": tier, "metric": "recall", "value": recall})
    pr_df = pd.DataFrame(rows).dropna()
    if not pr_df.empty:
        chart = (
            alt.Chart(pr_df)
            .mark_bar()
            .encode(
                x=alt.X("tier:O", title="Tier"),
                y=alt.Y("value:Q", title=None, scale=alt.Scale(domain=[0, 1])),
                color=alt.Color("metric:N", title=None),
                xOffset="metric:N",
                tooltip=["tier", "metric", alt.Tooltip("value:Q", format=".0%")],
            )
            .properties(height=280)
        )
        st.altair_chart(chart, use_container_width=True)

with right:
    st.subheader("Confusion matrix (gold vs. predicted)")
    if n:
        confusion = (
            joined.groupby(["gold_tier", "predicted_tier"]).size().reset_index(name="count")
        )
        heatmap = (
            alt.Chart(confusion)
            .mark_rect()
            .encode(
                x=alt.X("predicted_tier:O", title="Predicted tier"),
                y=alt.Y("gold_tier:O", title="Gold tier", sort="descending"),
                color=alt.Color("count:Q", scale=alt.Scale(scheme="blues")),
                tooltip=["gold_tier", "predicted_tier", "count"],
            )
            .properties(height=280)
        )
        text = heatmap.mark_text(baseline="middle").encode(
            text="count:Q", color=alt.value("black")
        )
        st.altair_chart(heatmap + text, use_container_width=True)

st.divider()
st.subheader("Tier-3 recall across runs")
trend = pd.read_sql(
    """
    SELECT p.run_id,
           SUM(CASE WHEN ec.gold_tier = 3 AND p.predicted_tier = 3 THEN 1 ELSE 0 END) * 1.0
             / NULLIF(SUM(CASE WHEN ec.gold_tier = 3 THEN 1 ELSE 0 END), 0) AS tier3_recall
    FROM eval_cases ec
    JOIN predictions p ON p.case_id = ec.id
    WHERE p.predicted_tier IS NOT NULL
    GROUP BY p.run_id
    ORDER BY p.run_id
    """,
    conn,
)
if len(trend) >= 2:
    line = (
        alt.Chart(trend)
        .mark_line(point=True)
        .encode(
            x=alt.X("run_id:N", title="Run"),
            y=alt.Y("tier3_recall:Q", title="Tier-3 recall", scale=alt.Scale(domain=[0, 1])),
            tooltip=["run_id", alt.Tooltip("tier3_recall:Q", format=".0%")],
        )
        .properties(height=250)
    )
    st.altair_chart(line, use_container_width=True)
else:
    st.caption("Run src/classify.py more than once to see a trend line here.")

st.divider()
st.subheader("Review queue")
queue = pd.read_sql(
    """
    SELECT rq.review_id, rq.case_id, rq.reason, rq.status, ec.text, ec.gold_tier
    FROM review_queue rq
    JOIN eval_cases ec ON ec.id = rq.case_id
    WHERE rq.run_id = ?
    ORDER BY
      CASE rq.reason WHEN 'critical_miss' THEN 0 WHEN 'disagreement' THEN 1 ELSE 2 END
    """,
    conn,
    params=(selected_run,),
)
if queue.empty:
    st.caption("Nothing in the review queue for this run.")
else:
    status_filter = st.multiselect(
        "Filter by status",
        sorted(queue["status"].unique()),
        default=list(queue["status"].unique()),
    )
    st.dataframe(
        queue[queue["status"].isin(status_filter)], hide_index=True, use_container_width=True
    )

decisions = pd.read_sql(
    """
    SELECT rd.reviewer, rd.decided_tier, rd.notes, rq.case_id
    FROM review_decisions rd
    JOIN review_queue rq ON rq.review_id = rd.review_id
    WHERE rq.run_id = ?
    """,
    conn,
    params=(selected_run,),
)
if not decisions.empty:
    st.subheader("QA reviewer decisions")
    st.dataframe(decisions, hide_index=True, use_container_width=True)

conn.close()
