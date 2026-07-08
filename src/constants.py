QUEST_STATUSES = ("Planned", "Completed", "Failed", "Skipped")

DEFAULT_CATEGORIES = (
    ("Health", "Fitness, nutrition, sleep, and recovery quests."),
    ("Work", "Professional tasks and focused work quests."),
    ("Learning", "Study, reading, and skill-building quests."),
    ("Home", "Chores, errands, and personal admin quests."),
    ("Social", "Relationships, family, and community quests."),
)

RPG_STATS = ("Strength", "Discipline", "Knowledge", "Recovery", "Creativity")
CATEGORY_TO_RPG_STAT = {
    "learning": "Knowledge",
    "health": "Strength",
    "work": "Discipline",
    "home": "Recovery",
    "social": "Creativity",
}
