# Metrics

This document defines the current core metrics for Habit Quest Analytics. After the QuestCheckin migration, daily completion metrics should use `QuestCheckin` records when they exist.

## XP Rewards

New scheduled quest and recurring habit XP is based on planned time.

```text
xp = max(5, round(planned_minutes / 60 * 20))
```

Examples:

| Planned minutes | XP |
| ---: | ---: |
| 15 | 5 |
| 30 | 10 |
| 60 | 20 |
| 90 | 30 |
| 120 | 40 |
| 180 | 60 |

Status: implemented in `src/services/xp_service.py`.

Notes:

- Scheduled quests use planned duration.
- Recurring habit templates use `estimated_minutes`.
- Existing stored quest/check-in XP is not retroactively recalculated.

## Total XP

```text
total_xp = sum(QuestCheckin.xp_awarded)
```

When check-ins exist, Character Profile uses awarded check-in XP. This prevents duplicate XP from repeated completion actions and preserves historical XP values.

Fallback:

- If no check-ins exist, legacy completed quest XP can be used so older demo data does not disappear.

## Level

```text
TotalXPForLevel(L) = round(100 * (L - 1)^1.4)
```

Level 1 starts at 0 XP. Character level is the highest level where
`total_xp >= TotalXPForLevel(level)`.

Examples:

| Level | Total XP required |
| ---: | ---: |
| 1 | 0 |
| 2 | 100 |
| 3 | 264 |
| 4 | 466 |
| 5 | 696 |
| 10 | 2167 |

Status: implemented in `src/services/xp_service.py`.

## XP To Next Level

```text
xp_to_next_level = TotalXPForLevel(current_level + 1) - total_xp
```

At exactly a level threshold, the character reaches that level and progress
toward the next threshold starts at 0%.

Status: implemented.

## Completed Quest Days

```text
completed_quest_days = count(check-ins where status = Completed)
```

This replaces the older "completed quests" interpretation in profile-style views when check-ins exist. A repeated habit can eventually produce many completed quest days from one parent quest.

## Command Center Metrics

Command Center is read-only and uses check-ins for operational status.

```text
planned_today = count(check-ins where status = Planned and checkin_date = today)
completed_today = count(check-ins where status = Completed and checkin_date = today)
overdue = count(check-ins where status = Planned and checkin_date < today)
failed = count(check-ins where status = Failed and checkin_date <= today)
```

Skipped check-ins are tracked separately and should not count as completed, failed, or overdue.

## Weekly XP

```text
weekly_xp = sum(xp_awarded for check-ins in the current week)
```

Normally only completed check-ins have nonzero XP.

## Weekly Completion Rate

```text
weekly_completion_rate = completed / (completed + failed) * 100
```

Rules:

- Use current-week check-ins.
- Exclude skipped check-ins.
- Exclude planned future check-ins.
- Return `0.0` if the denominator is zero.

## XP Trend By Day

```text
xp_by_day = sum(xp_awarded grouped by checkin_date)
```

The Habit Analytics trend chart uses check-in dates and a line chart with markers.

## Check-ins By Status

```text
checkins_by_status = count(check-ins grouped by status)
```

Supported status values:

- Planned
- Completed
- Failed
- Skipped

## Check-ins By Category

```text
checkins_by_category = count(check-ins grouped by parent quest category)
```

This joins `QuestCheckin -> Quest -> Category`.

## Completion Rate By Weekday

```text
weekday_completion_rate = completed / (completed + failed) * 100
```

Rules:

- Use `QuestCheckin.checkin_date`.
- Count completed and failed check-ins as resolved outcomes.
- Exclude skipped check-ins.
- Exclude planned items.
- Return `0.0` for weekdays without resolved check-ins.

## Planned Minutes By Category

```text
planned_minutes_by_category = sum(parent quest estimated_minutes grouped by category)
```

This represents planned workload attached to check-ins. It is not actual time spent.

## Goal Analytics

Goal analytics use long-term `Goal` records, one-time `Quest` sessions linked
through `Quest.goal_id`, and their `QuestCheckin` rows.

Recurring habits are not linked to goals in the current implementation and are
excluded from goal analytics.

### Goal Earned XP

```text
goal_earned_xp = sum(QuestCheckin.xp_awarded for linked goal sessions)
```

Goal XP is derived from linked session check-ins only. Goals do not award XP
directly, and expected goal XP is not counted as earned XP.

### Goal Completed Effort

```text
goal_completed_minutes = sum(Quest.estimated_minutes for completed linked check-ins)
```

Rules:

- Completed linked sessions contribute estimated minutes.
- Planned linked sessions do not contribute completed effort.
- Skipped and failed linked sessions do not contribute completed effort.
- Reset check-ins return to planned state with `xp_awarded = 0`, so they do not
  contribute completed effort or earned XP.
- Remaining effort is never below zero.
- Per-goal progress is capped at 100%.

### Goal Scheduling Effort

The Goal Session Planner uses scheduling effort to decide how many future
sessions can still be planned.

```text
effort_to_schedule_minutes =
    max(planned_total_minutes - completed_minutes - currently_planned_minutes, 0)
```

Rules:

- Completed linked check-ins reduce scheduling effort.
- Planned linked check-ins reduce scheduling effort.
- Failed and skipped linked check-ins do not reduce scheduling effort, so
  replacement sessions can be planned.
- Reset check-ins count according to their current `Planned` status.
- Scheduling effort never uses `QuestCheckin.xp_awarded`.
- Planning creates normal planned check-ins with `xp_awarded = 0`; XP is awarded
  only when a session is completed through the existing check-in flow.

### Weighted Overall Goal Progress

```text
overall_goal_progress =
    sum(completed_minutes across included goals)
    / sum(planned_total_minutes across included goals)
    * 100
```

Overall goal progress is weighted by planned effort. It is not a simple average
of individual goal percentages. The displayed value is capped between 0 and 100.

### Completed Goal Effort By Week

```text
completed_goal_effort_by_week =
    sum(Quest.estimated_minutes for completed linked check-ins grouped by checkin_date week)
```

The weekly trend uses `QuestCheckin.checkin_date` as the activity date.

## RPG Stat XP

```text
rpg_stat_xp = sum(xp_awarded for completed check-ins grouped by parent quest category RPG stat)
```

Default category mapping:

- Learning -> Knowledge
- Health -> Strength
- Work -> Discipline
- Social -> Creativity
- Home -> Recovery

Only completed check-ins with awarded XP contribute to stat XP. Planned,
skipped, failed, and reset check-ins with `xp_awarded = 0` do not contribute.

## RPG Stat Levels

```text
TotalXPForStatLevel(L) = round(60 * (L - 1)^1.35)
```

Level 1 starts at 0 XP. Stat level is the highest level where
`stat_xp >= TotalXPForStatLevel(level)`.

Examples:

| Stat level | Total XP required |
| ---: | ---: |
| 1 | 0 |
| 2 | 60 |
| 3 | 153 |
| 4 | 264 |

Character Profile stat bars show progress toward the next stat level. The radar
chart displays stat levels, not raw stat XP.

## Consistency Score

```text
consistency_score = completed_days / tracked_days * 100
```

Status: implemented as a pure metric helper. UI-level consistency currently uses check-in analytics views rather than a standalone streak system.

## Planned Metrics

### Current Streak

```text
current_streak = consecutive days with at least one completed habit quest day
```

Status: planned.

### Planned Vs Actual Time

```text
time_accuracy = actual_minutes / estimated_minutes * 100
```

Status: planned. The current data model includes `estimated_minutes`; an actual-time field is still needed before this metric can be implemented.
