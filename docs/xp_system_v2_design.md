# XP System v2 Design

This document defines XP System v2 for Habit Quest Analytics.

Current app context:

- Daily tracking uses `QuestCheckin`.
- Monthly Checklist resolves planned quest days.
- Recurring Habits v1 generates normal `Quest` and planned `QuestCheckin`
  records.
- Command Center, Character Profile, and Habit Analytics use check-in records as
  the main source of truth.
- Character Profile currently reads progression from `QuestCheckin.xp_awarded`.

XP System v2 should preserve that check-in source-of-truth model while changing
how future quest XP is calculated and displayed.

## Status

XP System v2 phases 1, 2, and 3 are implemented.

Implemented:

- New scheduled quests calculate XP from planned duration.
- New recurring habit templates calculate XP from estimated minutes.
- Generated recurring quests inherit template XP.
- Historical `Quest.xp_reward` and `QuestCheckin.xp_awarded` values are not
  retroactively recalculated.
- Character level and progress use nonlinear thresholds.
- RPG stat levels are derived from completed check-in XP by category.
- Character Profile stat panel and radar use stat levels.

Still planned:

- Long-term goals/projects.

## Product Goal

XP should primarily reward planned effort, not subjective difficulty.

The previous difficulty-based model was simple, but it made short "Hard" tasks
worth more than long focused work. XP System v2 makes planned time the
main XP driver so the RPG progression better reflects invested effort.

Difficulty may remain as a descriptive field for now. It should not be the main
XP driver in v2.

## Time-Based Quest XP

Use planned or estimated minutes as the main input.

Formula:

```text
XP = max(5, round(planned_minutes / 60 * 20))
```

Meaning:

- 20 XP per planned hour.
- Minimum 5 XP for short tasks.
- Use `estimated_minutes` or planned schedule duration.
- Do not add `actual_minutes` in v2.
- Do not retroactively recalculate historical XP unless a separate migration is
  explicitly designed later.

Examples:

| Planned minutes | XP |
| ---: | ---: |
| 15 | 5 |
| 30 | 10 |
| 60 | 20 |
| 90 | 30 |
| 120 | 40 |
| 180 | 60 |

Historical rule:

- Existing completed check-ins keep their stored `QuestCheckin.xp_awarded`.
- Future completions should award the stored XP from the quest/check-in flow.
- A separate explicit migration would be required to recalculate old data.

## Character Level Progression

Character level uses nonlinear thresholds.

Formula:

```text
TotalXPForLevel(L) = baseXP * (L - 1)^exponent
```

Constants:

```text
baseXP = 100
exponent = 1.4
```

XP to next level:

```text
XPToNextLevel(L) = TotalXPForLevel(L + 1) - TotalXPForLevel(L)
```

Rules:

- Level 1 starts at 0 XP.
- Character Total XP comes from `QuestCheckin.xp_awarded`.
- Level and progress should be calculated from total awarded check-in XP.
- Stored legacy `PlayerProfile.total_xp` should not become the main source of
  truth while check-ins exist.

Implementation note:

The level for a total XP value should be the highest level where
`TotalXPForLevel(level) <= total_xp`.

## Stat XP And Stat Levels

Stats:

- Strength
- Discipline
- Knowledge
- Recovery
- Creativity

Stats receive the same XP awarded by completed check-ins, mapped through the
parent quest category.

Category mapping:

| Category | Stat |
| --- | --- |
| Health | Strength |
| Work | Discipline |
| Learning | Knowledge |
| Home | Recovery |
| Social | Creativity |

Stat level formula:

```text
TotalXPForStatLevel(L) = statBaseXP * (L - 1)^statExponent
```

Constants:

```text
statBaseXP = 60
statExponent = 1.35
```

Stat levels grow slightly faster than character level because XP is split across
multiple stats. This should make category progress visible without making the
overall character level too fast.

## Character Profile Stat UI

The RPG stat section should use a compact stat panel design.

Each stat row should show:

- stat name on the left,
- horizontal progress/loading bar in the middle,
- current stat level on the right, such as `Lv. 4`.

Do not show values such as `7/10`. The bar should represent progress toward the
next stat level based on current stat XP within that level.

Example layout:

```text
Strength    [progress bar]    Lv. 4
Discipline  [progress bar]    Lv. 3
Knowledge   [progress bar]    Lv. 5
Recovery    [progress bar]    Lv. 2
Creativity  [progress bar]    Lv. 3
```

Optional helper text can show the XP distance to the next level, for example:

```text
35 / 80 XP to next level
```

Keep the visual design clean and compact.

Radar chart behavior:

- Display current stat levels, not raw stat XP.
- Make the radar chart visually larger inside the existing card/container.
- Do not enlarge the card/container itself.
- Achieved through Plotly layout and margin adjustments.

## App Impact

### Quest Planner

- One-time scheduled quests receive XP based on planned duration.
- XP reward should not be manually editable.
- Duration/time planning becomes the main XP driver.
- Difficulty can remain visible as descriptive metadata.

### Recurring Habits

- Recurring habit templates calculate XP from estimated minutes or
  planned duration.
- Generated quests inherit `xp_reward` from the recurring habit template.
- Completed generated check-ins award that stored XP once.

### Monthly Checklist

- Completion awards the stored quest/check-in XP.
- `QuestCheckin.xp_awarded` remains the durable record of awarded XP.
- Reset clears awarded XP as currently implemented.
- Skipped, failed, and planned check-ins award no XP.

### Character Profile

- Total XP comes from `QuestCheckin.xp_awarded`.
- Character level and progress use nonlinear thresholds.
- Stat XP and stat levels use category mapping.
- Stat panel shows progress bars and current stat levels.
- Radar chart uses stat levels.

### Habit Analytics

- Weekly XP uses `QuestCheckin.xp_awarded`.
- XP Trend uses `QuestCheckin.xp_awarded` grouped by check-in date.
- Planned time becomes more meaningful for analytics because XP is aligned with
  planned effort.

## Future Goals And Projects

Longer-term, the app can add a Goal or Project concept.

Planned fields:

- title
- category
- planned_total_minutes
- completed_minutes
- progress_percent
- status

Example:

A Portfolio Project planned for 20 hours can be split into 10 sessions of 2
hours. Each 2-hour session gives XP from planned time. The project aggregates
completed session minutes and XP.

This is not part of XP System v2. Keep it as future work.

## Implementation Phases

Phase status:

1. `docs: add xp system v2 design` - implemented.
2. `feat: calculate quest xp from planned time` - implemented.
3. `feat: add nonlinear character leveling` - implemented.
4. `feat: add stat leveling to character profile` - implemented.
5. `docs: update xp documentation` - ongoing as phases land.

## Test Plan

Add focused tests for:

- time-based XP formula,
- minimum XP,
- scheduled quests use time-based XP,
- recurring habit templates use time-based XP,
- generated recurring quests inherit template XP,
- completed check-ins award stored XP once,
- character level thresholds,
- XP to next level,
- stat XP grouping,
- stat levels,
- stat progress bar data,
- radar chart uses stat levels,
- no retroactive recalculation unless explicitly requested.

## Non-Goals For XP System v2

- No `actual_minutes` field.
- No retroactive historical XP recalculation by default.
- No project/goal aggregate model.
- No achievements overhaul.
- No machine learning.
- No external APIs.
- No production migration framework.
