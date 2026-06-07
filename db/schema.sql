PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    age INTEGER,
    height_cm REAL,
    weight_kg REAL,
    gender TEXT,
    activity_level TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fitness_goals (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    goal_type TEXT,
    target_weight_kg REAL,
    target_body_fat_pct REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS meal_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    diet_intensity TEXT NOT NULL DEFAULT 'normal'
        CHECK (diet_intensity IN ('normal', 'cheat', 'eating_out')),
    UNIQUE(user_id, day_of_week)
);

CREATE TABLE IF NOT EXISTS user_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'strength',
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS time_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workout_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_json TEXT NOT NULL,
    start_date TEXT NOT NULL,
    weeks INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id INTEGER REFERENCES workout_plans(id) ON DELETE SET NULL,
    event_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    duration_min INTEGER NOT NULL DEFAULT 45,
    completed INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS progress_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    logged_date TEXT NOT NULL,
    weight_kg REAL,
    body_fat_pct REAL,
    notes TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_calendar_events_user_date
    ON calendar_events(user_id, event_date);
CREATE INDEX IF NOT EXISTS idx_progress_logs_user_date
    ON progress_logs(user_id, logged_date);
