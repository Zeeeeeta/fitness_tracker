import json

import streamlit as st

from auth import (
    current_user_id,
    current_username,
    is_logged_in,
    render_auth_forms,
    render_logout_button,
)
from db import database as db
from services.plan_builder import monday_of_next_week

db.init_db()

st.set_page_config(page_title="Fitness App", page_icon="💪", layout="wide")

render_logout_button()


def render_dashboard(user_id: int) -> None:
    st.title("Dashboard")
    st.markdown(f"Welcome back, **{current_username()}**!")

    goal = db.get_goal(user_id)
    profile = db.get_profile(user_id)
    plan = db.get_active_plan(user_id)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Goal")
        if goal and goal.get("goal_type"):
            st.write(f"**{goal['goal_type'].replace('_', ' ').title()}**")
            if goal.get("target_weight_kg"):
                st.write(f"Target weight: {goal['target_weight_kg']} kg")
            if goal.get("target_body_fat_pct"):
                st.write(f"Target body fat: {goal['target_body_fat_pct']}%")
        else:
            st.info("Set your fitness goal on the Profile page.")

    with col2:
        st.subheader("Next week")
        week_start = monday_of_next_week()
        stats = db.get_week_completion_stats(user_id, week_start)
        if stats["total"] > 0:
            pct = int(stats["done"] / stats["total"] * 100)
            st.metric("Completion", f"{pct}%", f"{stats['done']}/{stats['total']} sessions")
            st.progress(pct / 100)
        else:
            st.info("No workouts scheduled next week. Generate a plan on Profile.")

    with col3:
        st.subheader("Current stats")
        if profile and profile.get("weight_kg"):
            st.metric("Weight", f"{profile['weight_kg']} kg")
        else:
            st.info("Add your health data on Profile.")

    if plan:
        try:
            plan_data = json.loads(plan["plan_json"])
            summary = plan_data.get("summary", "")
            if summary:
                st.markdown("---")
                st.subheader("Active plan")
                st.write(summary)
        except json.JSONDecodeError:
            pass

    st.markdown("---")
    st.markdown("Use the sidebar to navigate to **Profile**, **Calendar**, and **Progress**.")


if is_logged_in():
    render_dashboard(current_user_id())
else:
    st.title("Fitness App")
    st.caption("Your personalized workout calendar and progress tracker.")
    render_auth_forms()
