"""Measure account-scoped services against disposable, synthetic PostgreSQL data."""

import argparse
from calendar import Calendar
from collections import Counter
from datetime import date, datetime, time, timedelta
import hashlib
from importlib.metadata import version
import json
from math import ceil
import os
from pathlib import Path
import platform
from random import Random
from statistics import median
from time import perf_counter_ns
import tracemalloc
from unittest.mock import patch
from uuid import uuid4

import pandas as pd
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, func, insert, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.schema import CreateSchema, DropSchema


TODAY = date(2026, 7, 15)
DATABASE = "habit_quest_benchmark"
DATABASE_MARKER = "Habit Quest Analytics disposable benchmark"
# Check-ins, historical days, projects, and routine templates per account.
PROFILES = {
    "small": (1_000, 540, 8, 6),
    "medium": (10_000, 1_095, 24, 12),
    "large": (50_000, 1_825, 48, 24),
    "medium-many-projects": (10_000, 1_095, 72, 12),
}


def benchmark_url():
    configured = os.getenv("BENCHMARK_POSTGRESQL_URL")
    if not configured:
        raise SystemExit("Set BENCHMARK_POSTGRESQL_URL for the dedicated benchmark database.")
    try:
        url = make_url(configured)
    except (ArgumentError, ValueError):
        raise SystemExit("Invalid BENCHMARK_POSTGRESQL_URL.") from None
    if (
        url.drivername not in {"postgresql", "postgresql+psycopg"}
        or url.host != "127.0.0.1"
        or url.port is None
        or not 1024 <= url.port <= 65535
        or url.database != DATABASE
        or not url.username
        or not url.password
        or url.query
    ):
        raise SystemExit(f"Use an explicit loopback URL for {DATABASE}, with port and test credentials.")
    return url.set(drivername="postgresql+psycopg")


def benchmark_engine(url, schema="pg_catalog"):
    return create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "hostaddr": "127.0.0.1",
            "sslmode": "disable",
            "connect_timeout": 5,
            "options": f"-csearch_path={schema} -cstatement_timeout=120000",
        },
    )


def verify_target(engine):
    with engine.connect() as connection:
        name, host, marker, server_version = connection.exec_driver_sql(
            "SELECT current_database(), host(inet_server_addr()), "
            "shobj_description(oid, 'pg_database'), current_setting('server_version') "
            "FROM pg_database WHERE datname = current_database()"
        ).one()
        if (name, host, marker) != (DATABASE, "127.0.0.1", DATABASE_MARKER):
            raise SystemExit("The connection must reach the marked disposable database on loopback.")
        return server_version


def seed_account(connection, profile, account_number):
    from src.constants import DEFAULT_CATEGORIES
    from src.database.models import (
        Category, Goal, PlayerProfile, Quest, QuestCheckin, RecurringHabit, RecurringHabitInstance, UserAccount,
    )
    from src.services.quest_service import build_goal_session_title
    from src.services.xp_service import calculate_time_based_xp

    count, historical_days, project_count, routine_count = profile
    rng = Random(2050 + account_number)
    first_day = TODAY - timedelta(days=historical_days)
    last_day = TODAY + timedelta(days=14)
    created = datetime.combine(first_day, time(8))
    label = f"Synthetic {account_number}"
    owner = connection.scalar(insert(UserAccount).values(
        google_subject=f"benchmark-{account_number}", email=f"benchmark-{account_number}@example.invalid",
    ).returning(UserAccount.id))
    connection.execute(insert(PlayerProfile).values(
        user_id=owner, character_name=label, total_xp=0, created_at=created, updated_at=created,
    ))
    categories = connection.scalars(insert(Category).returning(Category.id, sort_by_parameter_order=True), [
        {"user_id": owner, "name": name, "description": description} for name, description in DEFAULT_CATEGORIES
    ]).all()
    statuses = ("Active", "Active", "Active", "Completed", "Archived")
    goals = [
        {
            "user_id": owner, "title": f"{label} project {index + 1:02}", "category_id": categories[index % 5],
            "status": statuses[index % 5], "start_date": first_day, "target_end_date": TODAY + timedelta(days=60),
            "planned_total_minutes": max(750, count * 45 // project_count),
            "created_at": created, "updated_at": created,
        }
        for index in range(project_count)
    ]
    goal_ids = connection.scalars(insert(Goal).returning(Goal.id, sort_by_parameter_order=True), goals).all()
    routines = [
        {
            "user_id": owner, "title": f"{label} routine {index + 1:02}", "category_id": categories[index % 5],
            "estimated_minutes": (15, 25, 40, 60)[index % 4], "recurrence_type": "daily",
            "planned_start_time": time(6 + index % 13), "start_date": first_day, "is_active": True,
            "created_at": created, "updated_at": created,
        }
        for index in range(routine_count)
    ]
    for routine in routines:
        routine["xp_reward"] = calculate_time_based_xp(routine["estimated_minutes"])
        routine["planned_end_time"] = (
            datetime.combine(first_day, routine["planned_start_time"]) + timedelta(minutes=routine["estimated_minutes"])
        ).time()
    routine_ids = connection.scalars(
        insert(RecurringHabit).returning(RecurringHabit.id, sort_by_parameter_order=True), routines,
    ).all()
    totals, types, session_numbers = Counter(), Counter(), Counter()
    xp_total = 0
    used_routines = set()
    day = None
    for batch_start in range(0, count, 1_000):
        quests, checkins, occurrences = [], [], []
        for index in range(batch_start, min(batch_start + 1_000, count)):
            scheduled = first_day + timedelta(days=index * ((last_day - first_day).days + 1) // count)
            if scheduled != day:
                used_routines.clear()
                day = scheduled
            start = time(7 + index % 12, 15 * (index % 4))
            duration = rng.choice((15, 25, 30, 45, 60, 90))
            category = rng.choice(categories)
            kind = rng.randrange(100)
            goal_id = number = None
            title = f"{label} task {index + 1}"
            routine_index = rng.randrange(routine_count)
            if kind < 26 and routine_index not in used_routines:
                used_routines.add(routine_index)
                routine = routines[routine_index]
                start, duration, category = routine["planned_start_time"], routine["estimated_minutes"], routine["category_id"]
                title = routine["title"]
                occurrences.append((len(quests), routine_ids[routine_index], day))
                types["routine"] += 1
            elif 26 <= kind < 49:
                goal_index = types["project"] % project_count
                goal_id = goal_ids[goal_index]
                session_numbers[goal_id] += 1
                number = session_numbers[goal_id]
                category = goals[goal_index]["category_id"]
                title = build_goal_session_title(goals[goal_index]["title"], number)
                types["project"] += 1
            else:
                types["one_time"] += 1
            start_at = datetime.combine(day, start)
            end_at = start_at + timedelta(minutes=duration)
            reward = calculate_time_based_xp(duration)
            status = (
                "Planned" if day >= TODAY else
                rng.choices(("Completed", "Skipped", "Failed", "Planned"), weights=(76, 12, 10, 2))[0]
            )
            earned = reward if status == "Completed" else 0
            quests.append({
                "user_id": owner, "title": title, "category_id": category, "due_date": day,
                "goal_id": goal_id, "goal_session_number": number, "is_habit": False, "status": "Planned",
                "planned_start_at": start_at, "planned_end_at": end_at, "estimated_minutes": duration,
                "xp_reward": reward, "created_at": created,
            })
            checkins.append({
                "user_id": owner, "checkin_date": day, "status": status, "xp_awarded": earned,
                "completed_at": end_at if status == "Completed" else None,
                "skipped_at": end_at if status == "Skipped" else None,
                "failed_at": end_at if status == "Failed" else None, "created_at": created, "updated_at": end_at,
            })
            totals[status] += 1
            xp_total += earned
        ids = connection.scalars(insert(Quest).returning(Quest.id, sort_by_parameter_order=True), quests).all()
        connection.execute(insert(QuestCheckin), [
            dict(values, quest_id=quest_id) for values, quest_id in zip(checkins, ids, strict=True)
        ])
        if occurrences:
            connection.execute(insert(RecurringHabitInstance), [
                {"user_id": owner, "recurring_habit_id": habit_id, "quest_id": ids[index],
                 "scheduled_date": scheduled, "created_at": created}
                for index, habit_id, scheduled in occurrences
            ])
    workload = {
        "account": owner, "quests": count, "checkins": count, "first_date": first_day, "last_date": day,
        "categories": len(categories), "checkin_statuses": totals, "types": types, "xp": xp_total,
        "projects": Counter(goal["status"] for goal in goals), "routines": routine_count,
        "work_category": categories[1], "selected_goal": goal_ids[0],
    }
    return workload


def operations(data):
    from src.services.analytics_service import (
        get_character_profile_data, get_goal_analytics_summary, get_habit_analytics_data,
    )
    from src.services.checklist_service import get_month_checklist
    from src.services.command_center_service import get_command_center_data
    from src.services.goal_service import get_goal_completion_forecast, get_goal_progress
    from src.services.quest_service import get_planner_schedule, get_quest_status_for_date

    def planner(session):
        weeks = Calendar().monthdatescalendar(TODAY.year, TODAY.month)
        schedule = get_planner_schedule(weeks[0][0], weeks[-1][-1], session=session)
        return {
            day.isoformat(): [(quest.id, get_quest_status_for_date(quest, day)) for quest in quests]
            for day, quests in schedule.items()
        }

    def analytics(session, days, **filters):
        return get_habit_analytics_data(
            today=TODAY, start_date=TODAY - timedelta(days=days - 1), end_date=TODAY, session=session, **filters,
        )

    def profile_indicator(profile):
        assert profile["total_xp"] == data["xp"]
        assert profile["character_name"] == f'Synthetic {data["account"]}'
        return profile["completed_quests"]

    return {
        "planner": (planner, lambda data: sum(map(len, data.values()))),
        "checklist": (
            lambda s: get_month_checklist(TODAY.year, TODAY.month, session=s), lambda d: len(d["rows"]),
        ),
        "summary": (lambda s: get_command_center_data(today=TODAY, session=s), lambda d: d["total_quests"]),
        "habit_30": (lambda s: analytics(s, 30), lambda d: d["period_summary"]["checkins_count"]),
        "habit_365": (lambda s: analytics(s, 365), lambda d: d["period_summary"]["checkins_count"]),
        "habit_filtered": (
            lambda s: analytics(s, 365, category_id=data["work_category"], work_type="project_session"),
            lambda d: d["period_summary"]["checkins_count"],
        ),
        "portfolio": (lambda s: get_goal_analytics_summary(session=s), lambda d: d["included_goals_count"]),
        "project": (
            lambda s: (
                get_goal_progress(data["selected_goal"], session=s),
                get_goal_completion_forecast(data["selected_goal"], today=TODAY, session=s),
            ),
            lambda d: d[0]["linked_sessions_count"],
        ),
        "profile": (lambda s: get_character_profile_data(today=TODAY, session=s), profile_indicator),
        "routine_streaks": (
            lambda s: analytics(s, 30, work_type="routine"), lambda d: len(d["routine_performance"]),
        ),
    }


def json_default(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, pd.DataFrame):
        return json.loads(value.to_json(orient="split", date_format="iso"))
    raise TypeError(f"Unsupported benchmark result value {type(value).__name__}.")


def normalized(value):
    # Checklist cells use date keys. The service's ordered lists are preserved.
    if isinstance(value, dict):
        return {str(key): normalized(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [normalized(item) for item in value]
    return value


class SqlRecorder:
    def __init__(self, engine):
        event.listen(engine, "before_cursor_execute", self.before)
        event.listen(engine, "after_cursor_execute", self.after)
        self.samples = []

    def before(self, connection, cursor, sql, params, context, many):
        context.benchmark_start_ns = perf_counter_ns()

    def after(self, connection, cursor, sql, params, context, many):
        self.samples.append((perf_counter_ns() - context.benchmark_start_ns, sql, params, many))


def explain_queries(engine, samples):
    # Profile the two most expensive distinct SELECT shapes in the warmed call.
    plans = []
    seen = set()
    with engine.connect() as connection:
        for _, sql, params, many in sorted(samples, key=lambda sample: sample[0], reverse=True):
            if many or not sql.lstrip().upper().startswith("SELECT") or sql in seen:
                continue
            seen.add(sql)
            plan = connection.exec_driver_sql("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params).scalar()[0]
            plans.append({"sql": sql, **plan})
            if len(plans) == 2:
                break
    return plans


def measure(engine, recorder, owner, operation, indicator, repeats, memory, explain):
    from src.database.user_session import UserSession

    def run():
        recorder.samples.clear()
        started = perf_counter_ns()
        with UserSession(bind=engine, user_id=owner, autoflush=False) as session:
            result = operation(session)
        return (perf_counter_ns() - started) / 1_000_000, result

    first, _ = run()
    first_sql = len(recorder.samples)
    run()  # One further warm-up after the first recorded invocation.
    durations, counts = [], []
    for _ in range(repeats):
        duration, result = run()
        durations.append(duration)
        counts.append(len(recorder.samples))
    last_samples = list(recorder.samples)
    encoded = json.dumps(normalized(result), default=json_default, sort_keys=True, ensure_ascii=True)
    result_info = {
        "first_ms": first, "first_sql": first_sql, "median_ms": median(durations),
        "p95_ms": sorted(durations)[ceil(0.95 * repeats) - 1],
        "sql_min": min(counts), "sql_max": max(counts), "indicator": indicator(result),
        "fingerprint": hashlib.sha256(encoded.encode()).hexdigest(),
    }
    del result, encoded
    if memory:
        tracemalloc.start()
        try:
            run()
            result_info["peak_mib"] = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
        finally:
            tracemalloc.stop()
    if explain:
        result_info["plans"] = explain_queries(engine, last_samples)
    return result_info


def measure_legacy_backfill(engine, recorder, owner, operation):
    from src.database.models import Quest, QuestCheckin
    from src.database.user_session import UserSession

    day = TODAY - timedelta(days=3)
    with engine.begin() as connection:
        ids = connection.scalars(insert(Quest).returning(Quest.id), [
            {"user_id": owner, "title": f"Legacy benchmark task {index + 1}", "due_date": day,
             "created_at": datetime.combine(day, time(9))}
            for index in range(24)
        ]).all()
    samples = []
    for _ in range(2):
        recorder.samples.clear()
        started = perf_counter_ns()
        with UserSession(bind=engine, user_id=owner, autoflush=False) as session:
            operation(session)
        samples.append({"ms": (perf_counter_ns() - started) / 1_000_000, "sql": len(recorder.samples)})
    with engine.connect() as connection:
        added = connection.scalar(select(func.count()).select_from(QuestCheckin).where(QuestCheckin.quest_id.in_(ids)))
    assert added == len(ids)
    return {"created_checkins": added, "first_run": samples[0], "next_run": samples[1]}


def run_profile(admin, url, name, repetition_count, memory, explain):
    from src.database import db
    from src.database.models import Base

    schema = f"hq_bench_{uuid4().hex}"
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = benchmark_engine(url, schema)
    try:
        config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
        with patch.multiple(db, DATABASE_URL=url, engine=engine):
            command.upgrade(config, "head")
        with engine.begin() as connection:
            accounts = [seed_account(connection, PROFILES[name], number) for number in (1, 2)]
            for table in Base.metadata.sorted_tables:
                connection.exec_driver_sql(f"ANALYZE {table.name}")
        primary, other = accounts
        assert primary["xp"] != other["xp"]
        recorder = SqlRecorder(engine)
        results = {}
        services = operations(primary)
        for label, (service, indicator) in services.items():
            result = measure(
                engine, recorder, primary["account"], service, indicator, repetition_count, memory,
                explain and name == "large" and label in {"planner", "checklist", "habit_365", "portfolio", "profile"},
            )
            results[label] = result
            print(f"{name:22} {label:16} {result['median_ms']:9.1f} ms  {result['sql_max']:4} SQL", flush=True)
        backfills = {
            label: measure_legacy_backfill(engine, recorder, primary["account"], services[label][0])
            for label in ("summary", "checklist")
        } if name == "medium" else {}
        return {
            "accounts": accounts,
            "operations": results,
            "legacy_backfills": backfills,
        }
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", nargs="+", choices=PROFILES, default=list(PROFILES))
    parser.add_argument("--repeats", type=int, default=25, help="Warm repetitions per operation (minimum 20).")
    parser.add_argument("--no-memory", action="store_true", help="Skip the separate Python allocation run.")
    parser.add_argument("--explain", action="store_true", help="Include selected large-profile execution plans in JSON.")
    parser.add_argument("--output", type=Path, required=True, help="Write JSON results to this path.")
    args = parser.parse_args()
    if args.repeats < 20:
        parser.error("--repeats must be at least 20")
    url = benchmark_url()
    # Alembic imports the app database module. Only the isolated engine below is configured.
    with patch.dict(os.environ):
        os.environ.pop("DATABASE_URL", None)
        admin = benchmark_engine(url)
        try:
            server_version = verify_target(admin)
            output = {
                "environment": {
                    "os": platform.platform(), "python": platform.python_version(), "postgresql": server_version,
                    "logical_cpus": os.cpu_count(), "reference_date": TODAY, "repetitions": args.repeats,
                    "dependencies": {pkg: version(pkg) for pkg in ("SQLAlchemy", "alembic", "psycopg", "pandas", "streamlit")},
                },
                "profiles": {},
            }
            for name in args.sizes:
                output["profiles"][name] = run_profile(
                    admin, url, name, args.repeats, not args.no_memory, args.explain,
                )
                args.output.write_text(json.dumps(output, indent=2, default=json_default) + "\n", encoding="utf-8")
        finally:
            admin.dispose()


if __name__ == "__main__":
    main()
