# Data Model

The application uses SQLite locally through SQLAlchemy.

## Tables

### categories

Stores quest categories such as Health, Work, Learning, Home, and Social.

### quests

Stores tasks and habits represented as quests.

Key fields:

- title
- description
- difficulty
- status
- is_habit
- xp_reward
- due_date
- completed_at
- category_id

### player_profiles

Stores the player character name and total XP.

### achievements

Stores achievement definitions.

### unlocked_achievements

Links player profiles to achievements they have unlocked.
