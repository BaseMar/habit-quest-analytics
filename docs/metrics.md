# Metrics

This document defines the core metrics for Habit Quest Analytics. Some formulas are implemented in the scaffold; others describe the planned MVP analytics layer.

## XP Rewards

Quest XP is based on difficulty.

| Difficulty | XP |
| --- | ---: |
| Easy | 10 |
| Medium | 30 |
| Hard | 75 |
| Boss | 150 |

What it tells the user:

- how much progress a completed quest contributes,
- whether harder quests are meaningfully rewarded,
- how daily actions translate into character progression.

Status: implemented in `src/services/xp_service.py`.

## Total XP

```text
total_xp = sum(xp_reward for completed quests)
```

What it tells the user:

- cumulative progress across all completed work,
- long-term activity level,
- the base value used for character level.

Status: model field exists on `PlayerProfile`; workflow update logic is planned.

## Level

```text
level = total_xp // 500 + 1
```

What it tells the user:

- the character's current progression tier,
- a simple long-term reward for repeated completion.

Status: implemented in `src/services/xp_service.py`.

## XP To Next Level

```text
xp_to_next_level = 500 - (total_xp % 500)
```

If `total_xp` is exactly on a level boundary, the next level requires another `500` XP.

What it tells the user:

- how close the character is to leveling up,
- how much work remains before the next progression milestone.

Status: implemented.

## Completion Rate

```text
completion_rate = completed_quests / total_quests * 100
```

If there are no quests, completion rate is `0.0`.

What it tells the user:

- whether planned work is actually getting finished,
- whether the quest load is realistic,
- how completion changes over time.

Status: implemented as a pure metric function.

## Weekly XP

```text
weekly_xp = sum(xp_reward for quests completed during the week)
```

What it tells the user:

- how much progress was earned each week,
- whether productivity is increasing, falling, or staying stable,
- which weeks had unusually high or low activity.

Status: implemented for quests completed in the current week.

## XP By Day

```text
xp_by_day = sum(xp_reward for completed quests grouped by activity date)
```

The activity date uses `completed_at` when available and falls back to the planned date.

What it tells the user:

- which days produced the most XP,
- whether completed effort is clustered or consistent,
- how quest completion translates into daily progress.

Status: implemented.

## Quests By Status

```text
quests_by_status = count(quests grouped by status)
```

Supported status values:

- Planned
- Completed
- Failed
- Skipped

What it tells the user:

- how much work is still planned,
- how much work was completed,
- whether skipped or failed quests are accumulating.

Status: implemented.

## Quests By Category

```text
quests_by_category = count(quests grouped by category)
```

What it tells the user:

- which life or work areas receive the most attention,
- whether categories are balanced,
- which categories may be neglected.

Status: implemented.

## Current Streak

```text
current_streak = consecutive days with at least one completed habit quest
```

What it tells the user:

- whether habit activity is consistent,
- how long the current routine has been maintained,
- whether missed days are breaking momentum.

Status: planned.

## Consistency Score

```text
consistency_score = completed_days / tracked_days * 100
```

If there are no tracked days, consistency score is `0.0`.

What it tells the user:

- how often the user follows through across a tracked period,
- whether a habit is stable enough to be considered reliable.

Status: implemented as a pure metric function.

## Planned Vs Actual Time

```text
time_accuracy = actual_minutes / estimated_minutes * 100
```

Alternative view:

```text
time_delta = actual_minutes - estimated_minutes
```

What it tells the user:

- whether tasks are being underestimated or overestimated,
- which categories consume more time than expected,
- whether planning accuracy improves over time.

Status: planned. The current data model includes `estimated_minutes`; an actual-time field is still needed before this metric can be implemented.

## Estimated Minutes By Category

```text
estimated_minutes_by_category = sum(estimated_minutes grouped by category)
```

What it tells the user:

- where planned time is being allocated,
- which categories carry the largest planned workload,
- whether time planning is balanced across categories.

Status: implemented.

## RPG Stat XP

```text
rpg_stat_xp = sum(xp_reward for completed quests grouped by mapped category stat)
```

Default category mapping:

- Learning -> Knowledge
- Health -> Strength
- Work -> Discipline
- Social -> Creativity
- Home -> Recovery

What it tells the user:

- which RPG-style character traits are growing,
- how completed work is distributed across life areas,
- whether the character profile reflects balanced activity.

Status: implemented.
