from datetime import date

import plotly.graph_objects as go
import streamlit as st

from auth import render_logout_button, require_login
from db import database as db

db.init_db()
user_id = require_login()
render_logout_button()

st.title("Progress Tracking")

goal = db.get_goal(user_id) or {}
profile = db.get_profile(user_id) or {}

# --- Log form ---
st.header("Log entry")
with st.form("progress_form"):
    logged_date = st.date_input("Date", value=date.today())

    col1, col2 = st.columns(2)
    with col1:
        weight_unknown = st.checkbox("Weight unknown", value=False)
        weight_kg = None
        if not weight_unknown:
            weight_kg = st.number_input(
                "Weight (kg)", min_value=30.0, max_value=300.0,
                value=float(profile.get("weight_kg") or 70.0),
            )
    with col2:
        body_fat_unknown = st.checkbox("Body fat unknown", value=True)
        body_fat_pct = None
        if not body_fat_unknown:
            body_fat_pct = st.number_input(
                "Body fat (%)", min_value=3.0, max_value=60.0,
                value=float(goal.get("target_body_fat_pct") or 20.0),
            )

    notes = st.text_input("Notes (optional)")
    if st.form_submit_button("Save entry", type="primary"):
        if weight_unknown and body_fat_unknown and not notes.strip():
            st.error("Enter at least one measurement or a note.")
        else:
            db.add_progress_log(user_id, {
                "logged_date": logged_date.isoformat(),
                "weight_kg": weight_kg,
                "body_fat_pct": body_fat_pct,
                "notes": notes,
            })
            st.success("Entry saved.")
            st.rerun()

# --- History ---
st.header("History")
logs = db.get_progress_logs(user_id)

if not logs:
    st.info("No progress entries yet. Log your first measurement above.")
else:
    for log in logs:
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        with col1:
            st.write(log["logged_date"])
        with col2:
            st.write(f"{log['weight_kg']} kg" if log.get("weight_kg") is not None else "Unknown")
        with col3:
            st.write(f"{log['body_fat_pct']}%" if log.get("body_fat_pct") is not None else "Unknown")
        with col4:
            if st.button("Delete", key=f"del_{log['id']}"):
                db.delete_progress_log(log["id"], user_id)
                st.rerun()
        if log.get("notes"):
            st.caption(log["notes"])

    # --- Charts ---
    st.header("Trends")
    chart_logs = sorted(logs, key=lambda x: x["logged_date"])
    dates = [l["logged_date"] for l in chart_logs]
    weights = [l["weight_kg"] for l in chart_logs]
    body_fats = [l["body_fat_pct"] for l in chart_logs]

    if any(w is not None for w in weights):
        fig_weight = go.Figure()
        fig_weight.add_trace(go.Scatter(
            x=dates, y=weights, mode="lines+markers", name="Weight (kg)",
        ))
        if goal.get("target_weight_kg"):
            fig_weight.add_hline(
                y=goal["target_weight_kg"],
                line_dash="dash", line_color="green",
                annotation_text="Target weight",
            )
        fig_weight.update_layout(
            title="Weight over time", xaxis_title="Date", yaxis_title="kg", height=350,
        )
        st.plotly_chart(fig_weight, use_container_width=True)

    if any(b is not None for b in body_fats):
        fig_bf = go.Figure()
        fig_bf.add_trace(go.Scatter(
            x=dates, y=body_fats, mode="lines+markers", name="Body fat (%)",
        ))
        if goal.get("target_body_fat_pct"):
            fig_bf.add_hline(
                y=goal["target_body_fat_pct"],
                line_dash="dash", line_color="green",
                annotation_text="Target body fat",
            )
        fig_bf.update_layout(
            title="Body fat over time", xaxis_title="Date", yaxis_title="%", height=350,
        )
        st.plotly_chart(fig_bf, use_container_width=True)

    if profile.get("weight_kg") and logs:
        latest = logs[0]
        if latest.get("weight_kg"):
            delta = latest["weight_kg"] - profile["weight_kg"]
            st.metric(
                "Change since profile weight",
                f"{latest['weight_kg']} kg",
                f"{delta:+.1f} kg",
            )
