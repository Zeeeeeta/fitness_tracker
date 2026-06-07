PRESET_EXERCISES: dict[str, str] = {
    "Running": "cardio",
    "Cycling": "cardio",
    "Swimming": "cardio",
    "Walking": "cardio",
    "Rowing": "cardio",
    "Jump rope": "cardio",
    "Squats": "strength",
    "Deadlift": "strength",
    "Bench press": "strength",
    "Pull-ups": "strength",
    "Push-ups": "strength",
    "Lunges": "strength",
    "Shoulder press": "strength",
    "Plank": "strength",
    "Yoga": "flexibility",
    "Stretching": "flexibility",
    "Pilates": "flexibility",
}

CARDIO_KEYWORDS = ("run", "jog", "swim", "bike", "cycle", "walk", "cardio", "row", "hike")
FLEX_KEYWORDS = ("yoga", "stretch", "pilates", "flex", "mobility")


def categorize_exercise(name: str) -> str:
    stripped = name.strip()
    if not stripped:
        return "strength"
    if stripped in PRESET_EXERCISES:
        return PRESET_EXERCISES[stripped]
    lower = stripped.lower()
    if any(kw in lower for kw in CARDIO_KEYWORDS):
        return "cardio"
    if any(kw in lower for kw in FLEX_KEYWORDS):
        return "flexibility"
    return "strength"


def presets_by_category() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {"cardio": [], "strength": [], "flexibility": []}
    for name, category in PRESET_EXERCISES.items():
        grouped[category].append(name)
    for names in grouped.values():
        names.sort()
    return grouped


def parse_custom_exercises(text: str) -> list[dict[str, str]]:
    exercises: list[dict[str, str]] = []
    seen: set[str] = set()
    for part in text.replace("\n", ",").split(","):
        name = part.strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        exercises.append({"name": name, "category": categorize_exercise(name), "notes": ""})
    return exercises
