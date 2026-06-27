QUEST_STATUSES = ("Planned", "Completed", "Failed", "Skipped")
QUEST_DIFFICULTIES = ("Easy", "Medium", "Hard", "Boss")

DEFAULT_CATEGORIES = (
    ("Health", "Fitness, nutrition, sleep, and recovery quests."),
    ("Work", "Professional tasks and focused work quests."),
    ("Learning", "Study, reading, and skill-building quests."),
    ("Home", "Chores, errands, and personal admin quests."),
    ("Social", "Relationships, family, and community quests."),
)

RPG_STATS = ("Knowledge", "Strength", "Discipline", "Creativity", "Recovery")
CATEGORY_TO_RPG_STAT = {
    "learning": "Knowledge",
    "health": "Strength",
    "work": "Discipline",
    "home": "Recovery",
    "social": "Creativity",
}
