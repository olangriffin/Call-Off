from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.backend.models.package.deliverable import Deliverable
from app.backend.models.package.package import WorkPackage
from app.backend.models.package.revision import DeliverableRevision
from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_activity import ProgrammeActivity
from app.backend.models.programme.programme_revision import ProgrammeRevision
from app.backend.models.project import Project
from app.backend.services.package_readiness import (
    calculate_package_readiness,
    is_deliverable_complete,
    latest_approval,
    latest_revision,
)
from app.backend.services.status import is_complete_status, normalize_status


HEALTH_LABELS = {
    "on_track": "On Track",
    "at_risk": "At Risk",
    "critical": "Critical",
    "incomplete": "Incomplete",
    "inactive": "Inactive",
}

HEALTH_CSS_CLASSES = {
    "on_track": "badge-success",
    "at_risk": "badge-warning",
    "critical": "badge-critical",
    "incomplete": "badge-muted",
    "inactive": "badge-muted",
}


@dataclass(frozen=True, slots=True)
class HealthState:
    key: str
    label: str
    css_class: str


@dataclass(frozen=True, slots=True)
class DeliveryHealthSegment:
    package: WorkPackage
    health: HealthState


@dataclass(frozen=True, slots=True)
class ProjectHealthRow:
    project: Project
    overall_health: HealthState
    design_health: HealthState
    programme_health: HealthState
    procurement_health: HealthState
    data_completeness: int
    delivery_health: tuple[DeliveryHealthSegment, ...]


@dataclass(frozen=True, slots=True)
class PortfolioHealthCounts:
    on_track: int
    at_risk: int
    critical: int
    incomplete: int
    inactive: int


@dataclass(frozen=True, slots=True)
class DashboardOverview:
    project_count: int
    active_project_count: int
    health_counts: PortfolioHealthCounts
    project_health_rows: tuple[ProjectHealthRow, ...]

    @property
    def active_project_health_rows(self) -> tuple[ProjectHealthRow, ...]:
        return tuple(
            row
            for row in self.project_health_rows
            if row.overall_health.key != "inactive"
        )


def _health_state(key: str) -> HealthState:
    return HealthState(
        key=key,
        label=HEALTH_LABELS[key],
        css_class=HEALTH_CSS_CLASSES[key],
    )


def _as_date(value: date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def _due_health(
    due_date: date | None,
    *,
    today: date,
    upcoming_cutoff: date,
) -> str | None:
    if due_date is None:
        return None
    if due_date < today:
        return "critical"
    if due_date <= upcoming_cutoff:
        return "at_risk"
    return None


def _worst_health(*health_keys: str) -> str:
    precedence = {
        "on_track": 0,
        "incomplete": 1,
        "at_risk": 2,
        "critical": 3,
    }
    return max(health_keys, key=lambda key: precedence[key])


def _current_programme_activities(project: Project) -> list[ProgrammeActivity]:
    internal_programme = next(
        (
            programme
            for programme in project.programmes
            if programme.programme_type == "internal"
        ),
        None,
    )
    if internal_programme is None:
        return []

    return [
        activity
        for revision in internal_programme.revisions
        if revision.is_current
        for activity in revision.activities
        if not activity.is_summary
    ]


def _activity_is_scheduled(activity: ProgrammeActivity) -> bool:
    start_date = _as_date(activity.planned_start)
    finish_date = _as_date(activity.planned_finish)
    if activity.activity_type == "milestone":
        return start_date is not None or finish_date is not None
    return start_date is not None and finish_date is not None


def _activity_due_date(activity: ProgrammeActivity) -> date | None:
    return _as_date(activity.planned_finish) or _as_date(activity.planned_start)


def _design_health(
    project: Project,
    *,
    today: date,
    upcoming_cutoff: date,
) -> str:
    deliverables = [
        deliverable
        for package in project.work_packages
        for deliverable in package.deliverables
    ]
    if not deliverables:
        return "incomplete"

    health_keys: list[str] = []
    incomplete = False
    for deliverable in deliverables:
        if (
            deliverable.planned_issue_date is None
            or deliverable.required_approval_date is None
        ):
            incomplete = True

        if is_deliverable_complete(deliverable):
            continue

        for due_date in (
            deliverable.planned_issue_date,
            deliverable.required_approval_date,
        ):
            due_health = _due_health(
                due_date,
                today=today,
                upcoming_cutoff=upcoming_cutoff,
            )
            if due_health:
                health_keys.append(due_health)

        revision = latest_revision(deliverable)
        approval = latest_approval(revision) if revision else None
        if approval and not is_complete_status(approval.status):
            if approval.response_due_date is None:
                incomplete = True
            else:
                due_health = _due_health(
                    approval.response_due_date,
                    today=today,
                    upcoming_cutoff=upcoming_cutoff,
                )
                if due_health:
                    health_keys.append(due_health)

    if health_keys:
        return _worst_health(*health_keys)
    if incomplete:
        return "incomplete"
    return "on_track"


def _programme_health(
    project: Project,
    *,
    today: date,
    upcoming_cutoff: date,
) -> str:
    activities = _current_programme_activities(project)
    if not activities:
        return "incomplete"

    health_keys: list[str] = []
    incomplete = False
    for activity in activities:
        if not _activity_is_scheduled(activity):
            incomplete = True
            continue
        if is_complete_status(activity.status):
            continue

        due_health = _due_health(
            _activity_due_date(activity),
            today=today,
            upcoming_cutoff=upcoming_cutoff,
        )
        if due_health:
            health_keys.append(due_health)

    if health_keys:
        return _worst_health(*health_keys)
    if incomplete:
        return "incomplete"
    return "on_track"


def _data_completeness(project: Project) -> int:
    """Measure the recorded fields needed to control a live project."""

    required_fields = 5
    completed_fields = sum(
        value is not None
        for value in (project.planned_start, project.planned_finish)
    )

    packages = list(project.work_packages)
    if packages:
        completed_fields += 1

    deliverables = [
        deliverable
        for package in packages
        for deliverable in package.deliverables
    ]
    if deliverables:
        completed_fields += 1

    activities = _current_programme_activities(project)
    if activities:
        completed_fields += 1

    for package in packages:
        required_fields += 3
        completed_fields += sum(
            value is not None
            for value in (
                package.planned_start,
                package.planned_finish,
                package.required_on_site_date,
            )
        )

    for deliverable in deliverables:
        required_fields += 2
        completed_fields += sum(
            value is not None
            for value in (
                deliverable.planned_issue_date,
                deliverable.required_approval_date,
            )
        )

    for activity in activities:
        if activity.activity_type == "milestone":
            required_fields += 1
            completed_fields += int(_activity_due_date(activity) is not None)
        else:
            required_fields += 2
            completed_fields += sum(
                value is not None
                for value in (activity.planned_start, activity.planned_finish)
            )

    return max(0, min(100, round((completed_fields / required_fields) * 100)))


def _delivery_health(
    project: Project,
    *,
    today: date,
) -> tuple[DeliveryHealthSegment, ...]:
    key_by_readiness = {
        "ready": "on_track",
        "in_progress": "on_track",
        "approaching": "at_risk",
        "at_risk": "at_risk",
        "critical": "critical",
        "setup_required": "incomplete",
    }
    return tuple(
        DeliveryHealthSegment(
            package=package,
            health=_health_state(
                key_by_readiness[
                    calculate_package_readiness(
                        list(package.deliverables),
                        package.required_on_site_date,
                        today=today,
                    ).key
                ]
            ),
        )
        for package in sorted(project.work_packages, key=lambda package: package.code)
    )


def _project_health_row(
    project: Project,
    *,
    today: date,
    upcoming_cutoff: date,
) -> ProjectHealthRow:
    if normalize_status(project.status) != "active":
        inactive = _health_state("inactive")
        return ProjectHealthRow(
            project=project,
            overall_health=inactive,
            design_health=inactive,
            programme_health=inactive,
            procurement_health=inactive,
            data_completeness=_data_completeness(project),
            delivery_health=(),
        )

    design_key = _design_health(
        project,
        today=today,
        upcoming_cutoff=upcoming_cutoff,
    )
    programme_key = _programme_health(
        project,
        today=today,
        upcoming_cutoff=upcoming_cutoff,
    )
    completeness = _data_completeness(project)
    overall_key = _worst_health(
        design_key,
        programme_key,
        "incomplete" if completeness < 100 else "on_track",
    )

    return ProjectHealthRow(
        project=project,
        overall_health=_health_state(overall_key),
        design_health=_health_state(design_key),
        programme_health=_health_state(programme_key),
        # Procurement has no source model today, so it is honest unknown data,
        # not a fabricated risk signal. Completeness covers assessable data.
        procurement_health=_health_state("incomplete"),
        data_completeness=completeness,
        delivery_health=_delivery_health(project, today=today),
    )


def get_dashboard_overview(
    database: Session,
    organization_id: str,
    *,
    today: date | None = None,
) -> DashboardOverview:
    """Return tenant-scoped project health prepared for the portfolio dashboard."""

    current_date = today or date.today()
    projects = list(
        database.scalars(
            select(Project)
            .where(Project.organization_id == organization_id)
            .order_by(Project.code)
            .options(
                selectinload(Project.work_packages)
                .selectinload(WorkPackage.deliverables)
                .selectinload(Deliverable.revisions)
                .selectinload(DeliverableRevision.approvals),
                selectinload(Project.programmes)
                .selectinload(Programme.revisions)
                .selectinload(ProgrammeRevision.activities),
            )
        ).all()
    )
    upcoming_cutoff = current_date + timedelta(days=14)
    rows = tuple(
        _project_health_row(
            project,
            today=current_date,
            upcoming_cutoff=upcoming_cutoff,
        )
        for project in projects
    )
    counts = {
        key: sum(row.overall_health.key == key for row in rows)
        for key in HEALTH_LABELS
    }

    return DashboardOverview(
        project_count=len(rows),
        active_project_count=len(rows) - counts["inactive"],
        health_counts=PortfolioHealthCounts(**counts),
        project_health_rows=rows,
    )
