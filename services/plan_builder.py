from datetime import date, timedelta
from typing import Any

from db import database as db
from services.llm_planner import WorkoutPlanResponse, WeeklySession


def monday_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def monday_of_next_week(d: date) -> date:
    return monday_of_week(d) + timedelta(days=7)


def expand_weekly_template(
    template: list[WeeklySession], start_date: date
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for session in template:
        event_date = start_date + timedelta(days=session.day_of_week)
        events.append(
            {
                "event_date": event_date.isoformat(),
                "start_time": session.start_time,
                "title": session.title,
                "description": session.description,
                "duration_min": session.duration_min,
            }
        )
    return events


def save_plan_to_db(user_id: int, plan: WorkoutPlanResponse) -> int:
    start = monday_of_next_week(date.today())
    start_iso = start.isoformat()

    db.delete_future_uncompleted_events(user_id, start_iso)

    plan_json = plan.model_dump_json()
    plan_id = db.save_workout_plan(user_id, plan_json, start_iso, 1)
    events = expand_weekly_template(plan.weekly_template, start)
    db.insert_calendar_events(user_id, plan_id, events)
    return plan_id
