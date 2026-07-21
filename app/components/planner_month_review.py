from calendar import month_name
from datetime import date
from html import escape

import streamlit as st

from src.services.checklist_service import get_month_checklist
from src.ui import render_empty_state


_STATUS_MARKERS = {
    None: "",
    "Planned": "P",
    "Completed": "C",
    "Skipped": "S",
    "Failed": "F",
}


def render_month_review_controls(selected_date: date) -> tuple[int, int]:
    """Render the persisted month selector and return its year and month."""
    if "checklist_month" not in st.session_state:
        st.session_state["checklist_month"] = selected_date.month
    if "checklist_year" not in st.session_state:
        st.session_state["checklist_year"] = selected_date.year

    month_col, year_col = st.columns([0.64, 0.36], vertical_alignment="bottom")
    with month_col:
        selected_month_name = st.selectbox(
            "Month",
            list(month_name)[1:],
            index=st.session_state["checklist_month"] - 1,
            key="checklist_month_name",
        )
        selected_month = list(month_name).index(selected_month_name)
        st.session_state["checklist_month"] = selected_month
    with year_col:
        selected_year = int(
            st.number_input(
                "Year",
                min_value=2000,
                max_value=2100,
                value=int(st.session_state["checklist_year"]),
                step=1,
                key="checklist_year_input",
            )
        )
        st.session_state["checklist_year"] = selected_year
    return selected_year, selected_month


def render_month_checklist(year: int, month: int) -> None:
    """Render the read-only checklist matrix and its status legend."""
    checklist = get_month_checklist(year, month)
    _render_checklist_legend()
    if not checklist["rows"]:
        render_empty_state(
            "No planned items for this month yet.",
            "Add tasks in the Add item tab to start tracking this month.",
        )
        return
    _render_checklist_table(checklist)


def _render_checklist_legend() -> None:
    legend_items = (
        ("-", "Not scheduled / locked"),
        ("P", "Planned"),
        ("C", "Completed"),
        ("S", "Skipped"),
        ("F", "Failed"),
    )
    legend_html = "".join(
        f'<span class="hq-legend-item"><span class="hq-legend-marker">{escape(marker)}</span>{escape(label)}</span>'
        for marker, label in legend_items
    )
    st.markdown(f'<div class="hq-legend-row">{legend_html}</div>', unsafe_allow_html=True)


def _render_checklist_table(checklist: dict) -> None:
    headers = ["Item", "Category"] + [str(day.day) for day in checklist["days"]]
    header_html = "".join(
        f'<th class="{"hq-table-sticky" if index == 0 else "hq-table-day" if index >= 2 else ""}">'
        f"{escape(header)}</th>"
        for index, header in enumerate(headers)
    )
    row_html = "\n".join(_render_checklist_table_row(row, checklist["days"]) for row in checklist["rows"])
    st.markdown(
        f"""
        <div class="hq-table-scroll">
            <table class="hq-data-table">
                <thead><tr>{header_html}</tr></thead>
                <tbody>{row_html}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_checklist_table_row(row: dict, days: list[date]) -> str:
    day_cells = "".join(
        f'<td class="hq-table-day">{_checklist_cell_marker_html(row["cells"][day])}</td>'
        for day in days
    )
    return (
        "<tr>"
        f'<td class="hq-table-sticky">{escape(str(row["title"]))}</td>'
        f'<td>{escape(str(row["category"] or "Uncategorized"))}</td>'
        f"{day_cells}"
        "</tr>"
    )


def _checklist_cell_marker_html(cell: dict) -> str:
    entries = cell.get("entries") or []
    if not entries:
        return _status_marker_html(cell.get("status"))

    status_counts: dict[str, int] = {}
    for entry in entries:
        status = entry.get("status")
        if status:
            status_counts[status] = status_counts.get(status, 0) + 1
    if not status_counts:
        return ""

    if len(status_counts) == 1:
        status, count = next(iter(status_counts.items()))
        marker = _STATUS_MARKERS.get(status, "")
        label = marker if count == 1 else f"{marker}{count}"
        return _status_marker_html(status, label=label)

    ordered_statuses = ("Completed", "Planned", "Skipped", "Failed")
    return " ".join(
        _status_marker_html(status, label=f"{_STATUS_MARKERS[status]}{status_counts[status]}")
        for status in ordered_statuses
        if status in status_counts
    )


def _status_marker_html(status: str | None, label: str | None = None) -> str:
    marker = _STATUS_MARKERS.get(status, "")
    if not marker:
        return ""
    label = label or marker
    status_class = {
        "Planned": "hq-status-planned",
        "Completed": "hq-status-completed",
        "Skipped": "hq-status-skipped",
        "Failed": "hq-status-failed",
    }.get(status, "hq-status-planned")
    return f'<span class="hq-status-marker {status_class}">{escape(label)}</span>'
