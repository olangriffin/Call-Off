from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.backend.models.programme.programme_activity import ProgrammeActivity


@dataclass(frozen=True)
class ProgrammeTimelineTick:
    label: str
    month_label: str
    left_px: int
    width_px: int


@dataclass(frozen=True)
class ProgrammeWorkspaceRow:
    activity: ProgrammeActivity
    depth: int
    start_date: date | None
    finish_date: date | None
    start_label: str
    finish_label: str
    duration_label: str
    status_label: str
    status_key: str
    search_text: str
    package_filter: str
    is_milestone: bool
    is_summary: bool
    is_unscheduled: bool
    bar_left_px: int | None
    bar_width_px: int | None


@dataclass(frozen=True)
class ProgrammeWorkspace:
    rows: list[ProgrammeWorkspaceRow]
    timeline_ticks: list[ProgrammeTimelineTick]
    timeline_width_px: int
    week_width_px: int
    timeline_start: date
    timeline_end: date
    today_left_px: int | None
    date_range_label: str
    activity_count: int
    milestone_count: int
    complete_count: int
    package_options: list[tuple[str, str]]


def _as_date(value: date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def _activity_dates(activity: ProgrammeActivity) -> tuple[date | None, date | None]:
    return _as_date(activity.planned_start), _as_date(activity.planned_finish)


def _is_milestone(activity: ProgrammeActivity) -> bool:
    return activity.activity_type == "milestone"


def _timeline_bounds(
    activity_rows: list[dict[str, Any]],
    today: date,
) -> tuple[date, date, date | None, date | None]:
    dated_points: list[date] = []

    for row in activity_rows:
        activity = row["activity"]
        start_date, finish_date = _activity_dates(activity)
        dated_points.extend(point for point in (start_date, finish_date) if point)

    if dated_points:
        first_date = min(dated_points)
        last_date = max(dated_points)
        scheduled_start = first_date
        scheduled_end = last_date
    else:
        first_date = today - timedelta(days=14)
        last_date = today + timedelta(days=28)
        scheduled_start = None
        scheduled_end = None

    timeline_start = first_date - timedelta(days=first_date.weekday() + 7)
    days_until_sunday = 6 - last_date.weekday()
    timeline_end = last_date + timedelta(days=days_until_sunday + 7)

    return timeline_start, timeline_end, scheduled_start, scheduled_end


def _pixels_per_day(day_count: int) -> int:
    if day_count <= 91:
        return 24
    if day_count <= 183:
        return 14
    return 8


def build_programme_workspace(
    activity_rows: list[dict[str, Any]],
    *,
    today: date | None = None,
) -> ProgrammeWorkspace:
    current_date = today or datetime.now(timezone.utc).date()
    (
        timeline_start,
        timeline_end,
        scheduled_start,
        scheduled_end,
    ) = _timeline_bounds(activity_rows, current_date)
    timeline_days = (timeline_end - timeline_start).days + 1
    day_width = _pixels_per_day(timeline_days)
    timeline_width = timeline_days * day_width

    timeline_ticks: list[ProgrammeTimelineTick] = []
    tick_date = timeline_start
    previous_month: tuple[int, int] | None = None

    while tick_date <= timeline_end:
        tick_end = min(tick_date + timedelta(days=6), timeline_end)
        tick_days = (tick_end - tick_date).days + 1
        month_key = (tick_date.year, tick_date.month)
        month_label = (
            tick_date.strftime("%b %Y") if month_key != previous_month else ""
        )
        timeline_ticks.append(
            ProgrammeTimelineTick(
                label=tick_date.strftime("%d %b"),
                month_label=month_label,
                left_px=(tick_date - timeline_start).days * day_width,
                width_px=tick_days * day_width,
            )
        )
        previous_month = month_key
        tick_date += timedelta(days=7)

    rows: list[ProgrammeWorkspaceRow] = []
    package_options: dict[str, str] = {}

    for source_row in activity_rows:
        activity = source_row["activity"]
        start_date, finish_date = _activity_dates(activity)
        is_milestone = _is_milestone(activity)
        milestone_date = finish_date or start_date
        is_scheduled = milestone_date is not None if is_milestone else (
            start_date is not None and finish_date is not None
        )

        if is_milestone and milestone_date:
            bar_left = (milestone_date - timeline_start).days * day_width
            bar_width = day_width
        elif is_scheduled and start_date and finish_date:
            bar_left = (start_date - timeline_start).days * day_width
            bar_width = max(((finish_date - start_date).days + 1) * day_width, 8)
        else:
            bar_left = None
            bar_width = None

        duration_minutes = activity.duration_minutes
        if duration_minutes:
            duration_days = duration_minutes / (8 * 60)
            duration_label = (
                f"{duration_days:g} day"
                if duration_days == 1
                else f"{duration_days:g} days"
            )
        else:
            duration_label = "—"

        work_package = activity.work_package
        package_filter = str(work_package.id) if work_package else "unassigned"
        if work_package:
            package_options[package_filter] = work_package.code

        status_key = activity.status if activity.status in {
            "not_started",
            "in_progress",
            "complete",
        } else "other"
        search_text = " ".join(
            part
            for part in (
                activity.activity_code,
                activity.name,
                work_package.code if work_package else "",
            )
            if part
        ).lower()

        rows.append(
            ProgrammeWorkspaceRow(
                activity=activity,
                depth=int(source_row["depth"]),
                start_date=start_date,
                finish_date=finish_date,
                start_label=(
                    start_date.strftime("%d %b %Y") if start_date else "Not set"
                ),
                finish_label=(
                    finish_date.strftime("%d %b %Y") if finish_date else "Not set"
                ),
                duration_label=duration_label,
                status_label=activity.status.replace("_", " ").title(),
                status_key=status_key,
                search_text=search_text,
                package_filter=package_filter,
                is_milestone=is_milestone,
                is_summary=activity.is_summary,
                is_unscheduled=not is_scheduled,
                bar_left_px=bar_left,
                bar_width_px=bar_width,
            )
        )

    today_left = None
    if timeline_start <= current_date <= timeline_end:
        today_left = (current_date - timeline_start).days * day_width

    return ProgrammeWorkspace(
        rows=rows,
        timeline_ticks=timeline_ticks,
        timeline_width_px=timeline_width,
        week_width_px=day_width * 7,
        timeline_start=timeline_start,
        timeline_end=timeline_end,
        today_left_px=today_left,
        date_range_label=(
            f"{scheduled_start.strftime('%d %b %Y')} – "
            f"{scheduled_end.strftime('%d %b %Y')}"
            if scheduled_start and scheduled_end
            else "No dates scheduled"
        ),
        activity_count=len(rows),
        milestone_count=sum(row.is_milestone for row in rows),
        complete_count=sum(row.activity.status == "complete" for row in rows),
        package_options=sorted(package_options.items(), key=lambda item: item[1]),
    )
