# Metrics

## XP Rewards

Quest XP is based on difficulty:

- Easy: 10 XP
- Medium: 30 XP
- Hard: 75 XP
- Boss: 150 XP

## Level Calculation

```text
level = total_xp // 500 + 1
```

## Completion Rate

```text
completion_rate = completed_quests / total_quests * 100
```

If there are no quests, completion rate is `0.0`.

## Consistency Score

```text
consistency_score = completed_days / tracked_days * 100
```

If there are no tracked days, consistency score is `0.0`.
