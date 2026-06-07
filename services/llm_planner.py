import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from anthropic import Anthropic
import streamlit as st

from db import database as db

DAY_NAMES = db.DAY_NAMES

GOAL_TYPE_DESCRIPTIONS = {
    "lose_weight": "Fat loss focus with cardio and moderate strength.",
    "gain_muscle": "Muscle gain focus with progressive strength training.",
    "lose_weight_and_gain_muscle": "Combine strength training with moderate cardio for fat loss and muscle gain.",
    "maintain": "Maintain current fitness with balanced training.",
    "recomposition": "Body recomposition: lose fat and gain muscle with minimal weight change.",
}

DIET_INTENSITY_DESCRIPTIONS = {
    "normal": "Standard training nutrition.",
    "cheat": "Higher calorie day; lighter workout intensity is acceptable.",
    "eating_out": "Less control over macros; prefer flexible or cardio sessions.",
}


class WeeklySession(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    title: str
    duration_min: int = Field(ge=15, le=180)
    description: str = ""

    @field_validator("start_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("start_time must be HH:MM")
        return v


class WorkoutPlanResponse(BaseModel):
    summary: str
    weekly_template: list[WeeklySession]


def _time_to_minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _session_fits_slot(session: WeeklySession, slots: list[dict[str, Any]]) -> bool:
    day_slots = [s for s in slots if s["day_of_week"] == session.day_of_week]
    if not day_slots:
        return False
    start = _time_to_minutes(session.start_time)
    end = start + session.duration_min
    for slot in day_slots:
        slot_start = _time_to_minutes(slot["start_time"])
        slot_end = _time_to_minutes(slot["end_time"])
        if start >= slot_start and end <= slot_end:
            return True
    return False


def validate_plan_against_slots(
    plan: WorkoutPlanResponse, user_id: int
) -> list[str]:
    slots = db.get_time_slots(user_id)
    errors = []
    for session in plan.weekly_template:
        if not _session_fits_slot(session, slots):
            day = DAY_NAMES[session.day_of_week]
            errors.append(
                f"{session.title} on {day} at {session.start_time} "
                f"({session.duration_min} min) does not fit any available slot."
            )
    return errors


def _format_target(value: Any, suffix: str) -> str:
    if value is None:
        return "not set"
    return f"{value}{suffix}"


def build_prompt(context: dict[str, Any]) -> str:
    profile = context["profile"]
    goal = context["goal"]
    goal_type = goal.get("goal_type", "unknown")
    goal_desc = GOAL_TYPE_DESCRIPTIONS.get(goal_type, "")

    lines = [
        "Create a weekly workout template for the UPCOMING week only. "
        "Generate exactly one week of sessions (Monday through Sunday of next week). "
        "Sessions MUST only be scheduled inside the provided time slots.",
        "",
        "## Health profile",
        f"- Age: {profile.get('age', 'unknown')}",
        f"- Height: {profile.get('height_cm', 'unknown')} cm",
        f"- Weight: {profile.get('weight_kg', 'unknown')} kg",
        f"- Gender: {profile.get('gender', 'unknown')}",
        f"- Activity level: {profile.get('activity_level', 'unknown')}",
        "",
        "## Fitness goal",
        f"- Type: {goal_type}",
        f"- Goal meaning: {goal_desc}",
        f"- Target weight: {_format_target(goal.get('target_weight_kg'), ' kg')}",
        f"- Target body fat: {_format_target(goal.get('target_body_fat_pct'), '%')}",
        f"- Notes: {goal.get('notes', '')}",
        "",
        "## Weekly diet intensity (adjust workout intensity accordingly)",
    ]
    for day_info in context["diet_plan"]:
        intensity = day_info["diet_intensity"]
        desc = DIET_INTENSITY_DESCRIPTIONS.get(intensity, intensity)
        lines.append(f"- {day_info['day']}: {intensity} — {desc}")

    lines.append("")
    lines.append("## Preferred exercises")
    for ex in context["exercises"]:
        lines.append(f"- {ex['name']} ({ex['category']})")

    lines.append("")
    lines.append("## Available time slots (day_of_week: 0=Monday … 6=Sunday)")
    for day_info in context["time_slots"]:
        if day_info["slots"]:
            slot_str = ", ".join(
                f"{s['start']}-{s['end']}" for s in day_info["slots"]
            )
            lines.append(
                f"- {day_info['day']} (day_of_week={day_info['day_of_week']}): {slot_str}"
            )

    lines.extend(
        [
            "",
            "Return JSON with this exact structure:",
            '{ "summary": "One sentence goal summary (max 120 chars)", '
            '"weekly_template": ['
            '{"day_of_week": 0, "start_time": "07:00", "title": "...", '
            '"duration_min": 45, "description": ""}]}',
            "",
            "Rules:",
            "- Generate exactly one week of sessions for the upcoming week",
            "- Use only day_of_week values where slots exist",
            "- start_time must fall within a slot; duration must fit inside it",
            "- Prefer the user's listed exercises where appropriate",
            "- Align intensity with goal type and daily diet intensity",
            "- Include rest/recovery days as needed",
            "- title should be short (e.g. 'Morning run', 'Upper body strength')",
            '- summary must be ONE sentence describing the week\'s training focus',
            "- Always set description to an empty string \"\" — do not include workout instructions",
        ]
    )
    return "\n".join(lines)


def generate_workout_plan(user_id: int) -> tuple[WorkoutPlanResponse | None, str | None]:
    api_key = st.secrets.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY not found in .streamlit/secrets.toml"

    context = db.get_user_context_for_llm(user_id)

    client = Anthropic(api_key=api_key)
    model = st.secrets.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=(
                "You are an expert fitness coach. "
                "Respond with valid JSON only, no markdown fences."
            ),
            messages=[{"role": "user", "content": build_prompt(context)}],
            temperature=0.4,
        )
        raw = response.content[0].text if response.content else ""
        data = json.loads(raw)
        if "progression_notes" in data:
            del data["progression_notes"]
        plan = WorkoutPlanResponse.model_validate(data)
    except json.JSONDecodeError as e:
        return None, f"LLM returned invalid JSON: {e}"
    except Exception as e:
        return None, f"Plan generation failed: {e}"

    slot_errors = validate_plan_against_slots(plan, user_id)
    if slot_errors:
        return None, "Plan validation failed:\n" + "\n".join(slot_errors)

    if not plan.weekly_template:
        return None, "LLM returned an empty weekly template."

    return plan, None
