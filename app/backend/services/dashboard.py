from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.backend.models.package.approval import Approval
from app.backend.models.package.deliverable import Deliverable
from app.backend.models.package.package import WorkPackage
from app.backend.models.package.revision import DeliverableRevision
from app.backend.models.project import Project
from app.backend.services.status import (
    is_complete_status_expression,
    normalize_status_expression,
)


@dataclass(frozen=True, slots=True)
class DashboardAttentionItem:
    kind: str
    label: str
    context: str
    due_date: date
    is_overdue: bool
    url: str
    action_label: str


@dataclass(frozen=True, slots=True)
class DashboardOverview:
    project_count: int
    active_project_count: int
    work_package_count: int
    deliverable_count: int
    overdue_deadline_count: int
    attention_items: tuple[DashboardAttentionItem, ...]

    @property
    def overdue_count(self) -> int:
        """Compatibility alias for callers using the previous metric name."""

        return self.overdue_deadline_count


def _count(database: Session, statement) -> int:
    return int(database.scalar(statement) or 0)


def get_dashboard_overview(
    database: Session,
    organization_id: str,
    *,
    today: date | None = None,
    attention_limit: int = 8,
) -> DashboardOverview:
    """Return an uncapped tenant summary and a small, deadline-led work queue."""

    current_date = today or date.today()
    upcoming_cutoff = current_date + timedelta(days=14)

    project_scope = Project.organization_id == organization_id
    incomplete_package = ~is_complete_status_expression(WorkPackage.status)
    incomplete_deliverable = ~is_complete_status_expression(
        Deliverable.status
    )

    project_count = _count(
        database,
        select(func.count(Project.id)).where(project_scope),
    )
    active_project_count = _count(
        database,
        select(func.count(Project.id)).where(
            project_scope,
            normalize_status_expression(Project.status) == "active",
        ),
    )
    work_package_count = _count(
        database,
        select(func.count(WorkPackage.id))
        .join(Project, WorkPackage.project_id == Project.id)
        .where(project_scope),
    )
    deliverable_count = _count(
        database,
        select(func.count(Deliverable.id))
        .join(WorkPackage, Deliverable.work_package_id == WorkPackage.id)
        .join(Project, WorkPackage.project_id == Project.id)
        .where(project_scope),
    )

    approval_scope = (
        select(
            Approval.id,
            Approval.response_due_date,
            Approval.reviewer_name,
            DeliverableRevision.id.label("revision_id"),
            Deliverable.reference.label("deliverable_reference"),
            Deliverable.id.label("deliverable_id"),
            Deliverable.name.label("deliverable_name"),
            WorkPackage.id.label("work_package_id"),
            WorkPackage.code.label("work_package_code"),
            Project.id.label("project_id"),
            Project.code.label("project_code"),
        )
        .join(
            DeliverableRevision,
            Approval.revision_id == DeliverableRevision.id,
        )
        .join(
            Deliverable,
            DeliverableRevision.deliverable_id == Deliverable.id,
        )
        .join(
            WorkPackage,
            Deliverable.work_package_id == WorkPackage.id,
        )
        .join(Project, WorkPackage.project_id == Project.id)
        .where(
            project_scope,
            Approval.response_due_date.is_not(None),
            Approval.response_due_date <= upcoming_cutoff,
            Approval.response_received_date.is_(None),
        )
    )

    # Each source is capped only after sorting. Fetching the first N from each
    # source is sufficient to determine the first N across their merged result.
    approval_rows = database.execute(
        approval_scope.order_by(Approval.response_due_date, Approval.id).limit(
            attention_limit
        )
    ).all()

    deliverable_columns = (
        Deliverable.id,
        Deliverable.reference,
        Deliverable.name,
        WorkPackage.id.label("work_package_id"),
        WorkPackage.code.label("work_package_code"),
        Project.id.label("project_id"),
        Project.code.label("project_code"),
    )
    deliverable_base = (
        select(*deliverable_columns)
        .join(WorkPackage, Deliverable.work_package_id == WorkPackage.id)
        .join(Project, WorkPackage.project_id == Project.id)
        .where(project_scope, incomplete_deliverable)
    )
    issue_rows = database.execute(
        deliverable_base.add_columns(
            Deliverable.planned_issue_date.label("due_date")
        )
        .where(
            Deliverable.planned_issue_date.is_not(None),
            Deliverable.planned_issue_date <= upcoming_cutoff,
        )
        .order_by(Deliverable.planned_issue_date, Deliverable.id)
        .limit(attention_limit)
    ).all()
    required_approval_rows = database.execute(
        deliverable_base.add_columns(
            Deliverable.required_approval_date.label("due_date")
        )
        .where(
            Deliverable.required_approval_date.is_not(None),
            Deliverable.required_approval_date <= upcoming_cutoff,
        )
        .order_by(Deliverable.required_approval_date, Deliverable.id)
        .limit(attention_limit)
    ).all()

    package_rows = database.execute(
        select(
            WorkPackage.id,
            WorkPackage.code,
            WorkPackage.name,
            WorkPackage.required_on_site_date,
            Project.id.label("project_id"),
            Project.code.label("project_code"),
        )
        .join(Project, WorkPackage.project_id == Project.id)
        .where(
            project_scope,
            incomplete_package,
            WorkPackage.required_on_site_date.is_not(None),
            WorkPackage.required_on_site_date <= upcoming_cutoff,
        )
        .order_by(WorkPackage.required_on_site_date, WorkPackage.id)
        .limit(attention_limit)
    ).all()

    attention_items: list[DashboardAttentionItem] = []
    for row in approval_rows:
        attention_items.append(
            DashboardAttentionItem(
                kind="approval_response",
                label=f"Approval response: {row.deliverable_name}",
                context=(
                    f"{row.project_code} / {row.work_package_code} / "
                    f"{row.deliverable_reference}"
                ),
                due_date=row.response_due_date,
                is_overdue=row.response_due_date < current_date,
                url=(
                    f"/app/projects/{row.project_id}/work-packages/"
                    f"{row.work_package_id}/deliverables/{row.deliverable_id}"
                    f"/revisions/{row.revision_id}/approvals/{row.id}/respond"
                ),
                action_label="Record response",
            )
        )

    for kind, rows, prefix in (
        ("deliverable_issue", issue_rows, "Issue"),
        (
            "deliverable_approval",
            required_approval_rows,
            "Approval required",
        ),
    ):
        for row in rows:
            attention_items.append(
                DashboardAttentionItem(
                    kind=kind,
                    label=f"{prefix}: {row.name}",
                    context=(
                        f"{row.project_code} / {row.work_package_code} / "
                        f"{row.reference}"
                    ),
                    due_date=row.due_date,
                    is_overdue=row.due_date < current_date,
                    url=(
                        f"/app/projects/{row.project_id}/work-packages/"
                        f"{row.work_package_id}/deliverables/{row.id}"
                    ),
                    action_label="View deliverable",
                )
            )

    for row in package_rows:
        attention_items.append(
            DashboardAttentionItem(
                kind="package_on_site",
                label=f"Required on site: {row.name}",
                context=f"{row.project_code} / {row.code}",
                due_date=row.required_on_site_date,
                is_overdue=row.required_on_site_date < current_date,
                url=(
                    f"/app/projects/{row.project_id}/work-packages/{row.id}"
                ),
                action_label="View package",
            )
        )

    attention_items.sort(
        key=lambda item: (item.due_date, item.kind, item.label)
    )

    overdue_approval_count = _count(
        database,
        select(func.count(Approval.id))
        .join(
            DeliverableRevision,
            Approval.revision_id == DeliverableRevision.id,
        )
        .join(
            Deliverable,
            DeliverableRevision.deliverable_id == Deliverable.id,
        )
        .join(
            WorkPackage,
            Deliverable.work_package_id == WorkPackage.id,
        )
        .join(Project, WorkPackage.project_id == Project.id)
        .where(
            project_scope,
            Approval.response_received_date.is_(None),
            Approval.response_due_date < current_date,
        ),
    )
    overdue_issue_count = _count(
        database,
        select(func.count(Deliverable.id))
        .join(WorkPackage, Deliverable.work_package_id == WorkPackage.id)
        .join(Project, WorkPackage.project_id == Project.id)
        .where(
            project_scope,
            incomplete_deliverable,
            Deliverable.planned_issue_date < current_date,
        ),
    )
    overdue_required_approval_count = _count(
        database,
        select(func.count(Deliverable.id))
        .join(WorkPackage, Deliverable.work_package_id == WorkPackage.id)
        .join(Project, WorkPackage.project_id == Project.id)
        .where(
            project_scope,
            incomplete_deliverable,
            Deliverable.required_approval_date < current_date,
        ),
    )
    overdue_package_count = _count(
        database,
        select(func.count(WorkPackage.id))
        .join(Project, WorkPackage.project_id == Project.id)
        .where(
            project_scope,
            incomplete_package,
            WorkPackage.required_on_site_date < current_date,
        ),
    )

    return DashboardOverview(
        project_count=project_count,
        active_project_count=active_project_count,
        work_package_count=work_package_count,
        deliverable_count=deliverable_count,
        overdue_deadline_count=(
            overdue_approval_count
            + overdue_issue_count
            + overdue_required_approval_count
            + overdue_package_count
        ),
        attention_items=tuple(attention_items[:attention_limit]),
    )
