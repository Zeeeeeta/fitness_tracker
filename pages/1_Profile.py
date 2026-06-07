import streamlit as st

from auth import render_logout_button, require_login
from db import database as db
from services.exercise_presets import (
    PRESET_EXERCISES,
    parse_custom_exercises,
    presets_by_category,
)
from services.llm_planner import generate_workout_plan
from services.plan_builder import save_plan_to_db

db.init_db()
user_id = require_login()
render_logout_button()

st.title("Profile & Plan Setup")

DAY_NAMES = db.DAY_NAMES
ACTIVITY_LEVELS = ["sedentary", "light", "moderate", "active", "very_active"]
GOAL_TYPES = [
    "lose_weight",
    "gain_muscle",
    "lose_weight_and_gain_muscle",
    "maintain",
    "recomposition",
]
GOAL_LABELS = {
    "lose_weight": "Lose weight",
    "gain_muscle": "Gain muscle",
    "lose_weight_and_gain_muscle": "Lose weight & gain muscle",
    "maintain": "Maintain",
    "recomposition": "Recomposition",
}
GOAL_CAPTIONS = {
    "lose_weight": "Focus on fat loss with cardio and moderate strength.",
    "gain_muscle": "Build muscle with progressive strength training.",
    "lose_weight_and_gain_muscle": "Combine strength training with moderate cardio for fat loss and muscle gain.",
    "maintain": "Keep your current fitness level with balanced training.",
    "recomposition": "Lose fat and gain muscle with minimal weight change; focus on body composition.",
}
DIET_OPTIONS = ["normal", "cheat", "eating_out"]
DIET_LABELS = {
    "normal": "Normal",
    "cheat": "Cheat day",
    "eating_out": "Eating out",
}
STEP_LABELS = {
    1: "Health data",
    2: "Fitness goal",
    3: "Weekly diet",
    4: "Preferred exercises",
    5: "Time slots",
    6: "Generate plan",
}

profile = db.get_profile(user_id) or {}
goal = db.get_goal(user_id) or {}
meal_rows = {m["day_of_week"]: m.get("diet_intensity", "normal") for m in db.get_meal_plans(user_id)}
saved_exercises = db.get_exercises(user_id)
time_slots = db.get_time_slots(user_id)

step_key = f"profile_step_{user_id}"
if step_key not in st.session_state:
    st.session_state[step_key] = 6 if db.profile_has_basics(user_id) else 1

step = st.session_state[step_key]
st.progress(step / 6, text=f"Step {step} of 6: {STEP_LABELS[step]}")

if step > 1 and step < 6:
    if st.button("Back to previous step"):
        st.session_state[step_key] = step - 1
        st.rerun()

if step == 6 and db.profile_has_basics(user_id):
    with st.expander("Edit earlier sections"):
        cols = st.columns(5)
        for i, s in enumerate([1, 2, 3, 4, 5], start=0):
            with cols[i]:
                if st.button(STEP_LABELS[s], key=f"goto_step_{s}"):
                    st.session_state[step_key] = s
                    st.rerun()

# --- Step 1: Health ---
if step == 1:
    st.header("Health data")
    with st.form("health_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            age = st.number_input("Age", min_value=10, max_value=120, value=profile.get("age") or 30)
            gender = st.selectbox(
                "Gender",
                ["", "male", "female", "other"],
                index=(
                    ["", "male", "female", "other"].index(profile.get("gender") or "")
                    if profile.get("gender") in ["male", "female", "other"]
                    else 0
                ),
            )
        with col2:
            height_cm = st.number_input(
                "Height (cm)", min_value=100.0, max_value=250.0,
                value=float(profile.get("height_cm") or 170.0),
            )
            weight_kg = st.number_input(
                "Weight (kg)", min_value=30.0, max_value=300.0,
                value=float(profile.get("weight_kg") or 70.0),
            )
        with col3:
            activity_level = st.selectbox(
                "Activity level",
                ACTIVITY_LEVELS,
                index=ACTIVITY_LEVELS.index(profile.get("activity_level") or "moderate"),
            )
        if st.form_submit_button("Save and continue", type="primary"):
            db.upsert_profile(user_id, {
                "age": age,
                "height_cm": height_cm,
                "weight_kg": weight_kg,
                "gender": gender or None,
                "activity_level": activity_level,
            })
            st.session_state[step_key] = 2
            st.rerun()

# --- Step 2: Goal ---
elif step == 2:
    st.header("Fitness goal")
    with st.form("goal_form"):
        goal_type = st.selectbox(
            "Goal type",
            GOAL_TYPES,
            index=GOAL_TYPES.index(goal.get("goal_type") or "lose_weight"),
            format_func=lambda x: GOAL_LABELS.get(x, x),
        )
        st.caption(GOAL_CAPTIONS.get(goal_type, ""))

        st.caption("Fill at least one target (the other can be left unset).")
        col1, col2 = st.columns(2)
        with col1:
            set_target_weight = st.checkbox(
                "Set target weight",
                value=goal.get("target_weight_kg") is not None,
            )
            target_weight = None
            if set_target_weight:
                target_weight = st.number_input(
                    "Target weight (kg)", min_value=30.0, max_value=300.0,
                    value=float(
                        goal.get("target_weight_kg")
                        or profile.get("weight_kg")
                        or 70.0
                    ),
                )
        with col2:
            set_target_bf = st.checkbox(
                "Set target body fat",
                value=goal.get("target_body_fat_pct") is not None,
            )
            target_bf = None
            if set_target_bf:
                target_bf = st.number_input(
                    "Target body fat (%)", min_value=3.0, max_value=60.0,
                    value=float(goal.get("target_body_fat_pct") or 20.0),
                )
        notes = st.text_area("Notes", value=goal.get("notes") or "")
        if st.form_submit_button("Save and continue", type="primary"):
            if not set_target_weight and not set_target_bf:
                st.error("Set at least one target: weight or body fat.")
            else:
                db.upsert_goal(user_id, {
                    "goal_type": goal_type,
                    "target_weight_kg": target_weight if set_target_weight else None,
                    "target_body_fat_pct": target_bf if set_target_bf else None,
                    "notes": notes,
                })
                st.session_state[step_key] = 3
                st.rerun()

# --- Step 3: Diet ---
elif step == 3:
    st.header("Weekly diet intensity")
    st.caption("How strict is your diet each day? This helps adjust workout intensity.")
    with st.form("meals_form"):
        diet_inputs: dict[int, str] = {}
        for d in range(7):
            current = meal_rows.get(d, "normal")
            diet_inputs[d] = st.radio(
                DAY_NAMES[d],
                DIET_OPTIONS,
                index=DIET_OPTIONS.index(current) if current in DIET_OPTIONS else 0,
                format_func=lambda x: DIET_LABELS[x],
                horizontal=True,
                key=f"diet_{d}",
            )
        if st.form_submit_button("Save and continue", type="primary"):
            for d, intensity in diet_inputs.items():
                db.upsert_meal_plan(user_id, d, intensity)
            st.session_state[step_key] = 4
            st.rerun()

# --- Step 4: Exercises ---
elif step == 4:
    st.header("Preferred exercises")
    preset_names = set(PRESET_EXERCISES.keys())
    selected_presets = [ex["name"] for ex in saved_exercises if ex["name"] in preset_names]
    custom_saved = [ex["name"] for ex in saved_exercises if ex["name"] not in preset_names]
    grouped = presets_by_category()

    with st.form("exercises_form"):
        selected: list[str] = []
        for category, names in grouped.items():
            picked = st.multiselect(
                category.title(),
                names,
                default=[n for n in selected_presets if n in names],
                key=f"preset_{category}",
            )
            selected.extend(picked)
        custom_text = st.text_input(
            "Other exercises (comma-separated)",
            value=", ".join(custom_saved),
            placeholder="e.g. Rock climbing, Tennis",
        )
        if st.form_submit_button("Save and continue", type="primary"):
            exercises = [
                {"name": name, "category": PRESET_EXERCISES[name], "notes": ""}
                for name in selected
            ]
            exercises.extend(parse_custom_exercises(custom_text))
            if not exercises:
                st.error("Select at least one exercise.")
            else:
                db.replace_exercises(user_id, exercises)
                st.session_state[step_key] = 5
                st.rerun()

# --- Step 5: Time slots ---
elif step == 5:
    st.header("Available time slots")
    slot_key = f"slot_rows_{user_id}"
    if slot_key not in st.session_state:
        st.session_state[slot_key] = time_slots if time_slots else [
            {"day_of_week": 0, "start_time": "07:00", "end_time": "08:00"}
        ]

    for i, row in enumerate(st.session_state[slot_key]):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            st.session_state[slot_key][i]["day_of_week"] = st.selectbox(
                "Day", list(range(7)),
                format_func=lambda x: DAY_NAMES[x],
                index=row.get("day_of_week", 0),
                key=f"slot_day_{user_id}_{i}",
                label_visibility="collapsed",
            )
        with col2:
            st.session_state[slot_key][i]["start_time"] = st.text_input(
                "Start", value=row.get("start_time", "07:00"),
                key=f"slot_start_{user_id}_{i}",
                label_visibility="collapsed", placeholder="HH:MM",
            )
        with col3:
            st.session_state[slot_key][i]["end_time"] = st.text_input(
                "End", value=row.get("end_time", "08:00"),
                key=f"slot_end_{user_id}_{i}",
                label_visibility="collapsed", placeholder="HH:MM",
            )
        with col4:
            if st.button("Remove", key=f"slot_del_{user_id}_{i}"):
                st.session_state[slot_key].pop(i)
                st.rerun()

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("+ Add time slot"):
            st.session_state[slot_key].append(
                {"day_of_week": 0, "start_time": "07:00", "end_time": "08:00"}
            )
            st.rerun()
    with col_b:
        if st.button("Save and continue", type="primary"):
            if not st.session_state[slot_key]:
                st.error("Add at least one time slot.")
            else:
                db.replace_time_slots(user_id, st.session_state[slot_key])
                st.session_state[slot_key] = db.get_time_slots(user_id)
                st.session_state[step_key] = 6
                st.rerun()

# --- Step 6: Generate ---
elif step == 6:
    st.header("Generate workout calendar")
    st.caption(
        "Plans are AI-generated for next week only. "
        "Completing the calendar does not guarantee your goal — "
        "consult a professional for medical advice."
    )

    ready, missing = db.profile_ready_for_plan(user_id)
    if not ready:
        st.warning("Complete these before generating a plan: " + ", ".join(missing))
    else:
        st.success("Profile is ready for plan generation.")

    if st.button("Generate plan", type="primary", disabled=not ready):
        with st.spinner("Generating your workout calendar..."):
            plan, error = generate_workout_plan(user_id)
            if error:
                st.error(error)
            elif plan:
                save_plan_to_db(user_id, plan)
                st.switch_page("pages/2_Calendar.py")
