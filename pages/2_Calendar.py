import json
from datetime import timedelta

import streamlit as st

from auth import render_logout_button, require_login
from db import database as db
from services.plan_builder import monday_of_next_week

db.init_db()
user_id = require_login()
render_logout_button()

st.title("Workout Calendar")

DAY_NAMES = db.DAY_NAMES

week_start = monday_of_next_week()
week_end = week_start + timedelta(days=6)

st.subheader(f"Next week: {week_start.strftime('%b %d')} – {week_end.strftime('%b %d, %Y')}")

stats = db.get_week_completion_stats(user_id, week_start)
if stats["total"] > 0:
    pct = int(stats["done"] / stats["total"] * 100)
    st.progress(pct / 100, text=f"{stats['done']}/{stats['total']} sessions completed ({pct}%)")
else:
    st.info("No workouts scheduled for next week. Generate a plan on the Profile page.")

plan = db.get_active_plan(user_id)
if plan:
    try:
        plan_data = json.loads(plan["plan_json"])
        summary = plan_data.get("summary", "")
        if summary:
            st.info(summary)
    except json.JSONDecodeError:
        pass

events = db.get_events_for_week(user_id, week_start)

if not events:
    st.write("No events next week.")
else:
    events_by_day: dict[str, list] = {}
    for ev in events:
        events_by_day.setdefault(ev["event_date"], []).append(ev)

    for offset in range(7):
        day = week_start + timedelta(days=offset)
        day_iso = day.isoformat()
        day_events = events_by_day.get(day_iso, [])

        st.markdown(f"**{DAY_NAMES[offset]} — {day.strftime('%b %d')}**")
        if not day_events:
            st.caption("Rest day")
        else:
            for ev in day_events:
                col_check, col_info = st.columns([1, 10])
                with col_check:
                    completed = bool(ev["completed"])
                    new_val = st.checkbox(
                        "Done",
                        value=completed,
                        key=f"ev_{ev['id']}",
                        label_visibility="collapsed",
                    )
                    if new_val != completed:
                        db.set_event_completed(ev["id"], user_id, new_val)
                        st.rerun()
                with col_info:
                    status = "Done" if ev["completed"] else "Pending"
                    st.markdown(
                        f"**{ev['start_time']}** — {ev['title']} "
                        f"({ev['duration_min']} min) · {status}"
                    )
        st.divider()
