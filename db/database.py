import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent / "fitness.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DIET_INTENSITY_VALUES = ("normal", "cheat", "eating_out")


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _migrate_schema(conn: sqlite3.Connection) -> None:
    meal_cols = _table_columns(conn, "meal_plans")
    if meal_cols and "diet_intensity" not in meal_cols:
        conn.execute(
            "ALTER TABLE meal_plans ADD COLUMN diet_intensity TEXT NOT NULL DEFAULT 'normal'"
        )
        if "meals_text" in meal_cols:
            conn.execute("UPDATE meal_plans SET diet_intensity = 'normal'")


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
        _migrate_schema(conn)


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def monday_of_next_week(d: date | None = None) -> date:
    today = d or date.today()
    return today - timedelta(days=today.weekday()) + timedelta(days=7)


# --- Users ---


def create_user(username: str, password_hash: str) -> int | None:
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return row_to_dict(row)


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_dict(row)


# --- Profile ---


def get_profile(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row_to_dict(row)


def upsert_profile(user_id: int, data: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_profiles (user_id, age, height_cm, weight_kg, gender, activity_level, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                age = excluded.age,
                height_cm = excluded.height_cm,
                weight_kg = excluded.weight_kg,
                gender = excluded.gender,
                activity_level = excluded.activity_level,
                updated_at = datetime('now')
            """,
            (
                user_id,
                data.get("age"),
                data.get("height_cm"),
                data.get("weight_kg"),
                data.get("gender"),
                data.get("activity_level"),
            ),
        )


def get_goal(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM fitness_goals WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row_to_dict(row)


def upsert_goal(user_id: int, data: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO fitness_goals
                (user_id, goal_type, target_weight_kg, target_body_fat_pct, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                goal_type = excluded.goal_type,
                target_weight_kg = excluded.target_weight_kg,
                target_body_fat_pct = excluded.target_body_fat_pct,
                notes = excluded.notes
            """,
            (
                user_id,
                data.get("goal_type"),
                data.get("target_weight_kg"),
                data.get("target_body_fat_pct"),
                data.get("notes", ""),
            ),
        )


def get_meal_plans(user_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM meal_plans WHERE user_id = ? ORDER BY day_of_week",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_meal_plan(user_id: int, day_of_week: int, diet_intensity: str) -> None:
    if diet_intensity not in DIET_INTENSITY_VALUES:
        diet_intensity = "normal"
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO meal_plans (user_id, day_of_week, diet_intensity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, day_of_week) DO UPDATE SET
                diet_intensity = excluded.diet_intensity
            """,
            (user_id, day_of_week, diet_intensity),
        )


def get_exercises(user_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM user_exercises WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def replace_exercises(user_id: int, exercises: list[dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM user_exercises WHERE user_id = ?", (user_id,))
        for ex in exercises:
            if ex.get("name", "").strip():
                conn.execute(
                    """
                    INSERT INTO user_exercises (user_id, name, category, notes)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        ex["name"].strip(),
                        ex.get("category", "strength"),
                        ex.get("notes", ""),
                    ),
                )


def get_time_slots(user_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM time_slots WHERE user_id = ? ORDER BY day_of_week, start_time",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def replace_time_slots(user_id: int, slots: list[dict[str, Any]]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM time_slots WHERE user_id = ?", (user_id,))
        for slot in slots:
            conn.execute(
                """
                INSERT INTO time_slots (user_id, day_of_week, start_time, end_time)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, slot["day_of_week"], slot["start_time"], slot["end_time"]),
            )


# --- Workout plans & calendar ---


def save_workout_plan(
    user_id: int, plan_json: str, start_date: str, weeks: int = 1
) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO workout_plans (user_id, plan_json, start_date, weeks)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, plan_json, start_date, weeks),
        )
        return cur.lastrowid


def get_active_plan(user_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM workout_plans
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return row_to_dict(row)


def delete_future_uncompleted_events(user_id: int, from_date: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            DELETE FROM calendar_events
            WHERE user_id = ? AND event_date >= ? AND completed = 0
            """,
            (user_id, from_date),
        )


def insert_calendar_events(user_id: int, plan_id: int, events: list[dict[str, Any]]) -> None:
    with get_connection() as conn:
        for ev in events:
            conn.execute(
                """
                INSERT INTO calendar_events
                    (user_id, plan_id, event_date, start_time, title, description, duration_min)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    plan_id,
                    ev["event_date"],
                    ev["start_time"],
                    ev["title"],
                    ev.get("description", ""),
                    ev.get("duration_min", 45),
                ),
            )


def get_events_for_week(user_id: int, week_start: date) -> list[dict[str, Any]]:
    week_end = week_start + timedelta(days=6)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM calendar_events
            WHERE user_id = ? AND event_date >= ? AND event_date <= ?
            ORDER BY event_date, start_time
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]


def set_event_completed(event_id: int, user_id: int, completed: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE calendar_events
            SET completed = ?, completed_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                1 if completed else 0,
                datetime.now().isoformat() if completed else None,
                event_id,
                user_id,
            ),
        )


def get_week_completion_stats(user_id: int, week_start: date) -> dict[str, int]:
    week_end = week_start + timedelta(days=6)
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS done
            FROM calendar_events
            WHERE user_id = ? AND event_date >= ? AND event_date <= ?
            """,
            (user_id, week_start.isoformat(), week_end.isoformat()),
        ).fetchone()
        return {"total": row["total"] or 0, "done": row["done"] or 0}


# --- Progress logs ---


def add_progress_log(user_id: int, data: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO progress_logs (user_id, logged_date, weight_kg, body_fat_pct, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                data["logged_date"],
                data.get("weight_kg"),
                data.get("body_fat_pct"),
                data.get("notes", ""),
            ),
        )


def get_progress_logs(user_id: int, limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM progress_logs
            WHERE user_id = ?
            ORDER BY logged_date DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_progress_log(log_id: int, user_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM progress_logs WHERE id = ? AND user_id = ?",
            (log_id, user_id),
        )


# --- Profile completeness ---


def profile_ready_for_plan(user_id: int) -> tuple[bool, list[str]]:
    missing = []
    profile = get_profile(user_id)
    goal = get_goal(user_id)
    slots = get_time_slots(user_id)
    exercises = get_exercises(user_id)

    if not profile or not profile.get("weight_kg"):
        missing.append("Health profile (at least current weight)")
    if not goal or not goal.get("goal_type"):
        missing.append("Fitness goal")
    if not slots:
        missing.append("At least one available time slot")
    if not exercises:
        missing.append("At least one preferred exercise")

    return len(missing) == 0, missing


def profile_has_basics(user_id: int) -> bool:
    profile = get_profile(user_id)
    goal = get_goal(user_id)
    return bool(profile and profile.get("weight_kg") and goal and goal.get("goal_type"))


def get_user_context_for_llm(user_id: int) -> dict[str, Any]:
    profile = get_profile(user_id) or {}
    goal = get_goal(user_id) or {}
    meals = get_meal_plans(user_id)
    exercises = get_exercises(user_id)
    slots = get_time_slots(user_id)

    diet_by_day = {m["day_of_week"]: m.get("diet_intensity", "normal") for m in meals}
    diet_list = [
        {"day": DAY_NAMES[d], "day_of_week": d, "diet_intensity": diet_by_day.get(d, "normal")}
        for d in range(7)
    ]

    slots_by_day: dict[int, list[dict[str, str]]] = {d: [] for d in range(7)}
    for s in slots:
        slots_by_day[s["day_of_week"]].append(
            {"start": s["start_time"], "end": s["end_time"]}
        )

    return {
        "profile": profile,
        "goal": goal,
        "diet_plan": diet_list,
        "exercises": exercises,
        "time_slots": [
            {"day": DAY_NAMES[d], "day_of_week": d, "slots": slots_by_day[d]}
            for d in range(7)
        ],
    }
