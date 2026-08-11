from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from app.backend.models.package.approval import Approval
from app.backend.models.package.deliverable import Deliverable
from app.backend.models.package.revision import DeliverableRevision
from app.backend.services.status import is_complete_status


@dataclass(frozen=True, slots=True)
class PackageReadinessSummary:
    key: str
    label: str
    description: str
    css_class: str
    total_deliverables: int
    complete_deliverables: int
    overdue_issue_count: int
    overdue_approval_count: int
    missing_revision_count: int
    pending_approval_count: int

    @property
    def completion_percentage(self) -> int:
        if self.total_deliverables == 0:
            return 0

        return round(
            (self.complete_deliverables / self.total_deliverables) * 100
        )


def latest_revision(
    deliverable: Deliverable,
) -> DeliverableRevision | None:
    if not deliverable.revisions:
        return None

    return max(
        deliverable.revisions,
        key=lambda revision: (
            revision.issue_date or date.min,
            revision.revision_code,
        ),
    )


def latest_approval(
    revision: DeliverableRevision,
) -> Approval | None:
    if not revision.approvals:
        return None

    return max(
        revision.approvals,
        key=_approval_chronology_key,
    )


def _approval_chronology_key(
    approval: Approval,
) -> tuple[datetime, datetime, str]:
    created_at = getattr(approval, "created_at", None)
    if created_at is None:
        created_at_key = datetime.min
    elif created_at.tzinfo is None:
        created_at_key = created_at
    else:
        created_at_key = created_at.astimezone(timezone.utc).replace(
            tzinfo=None
        )

    submitted_date = getattr(approval, "submitted_date", None)
    chronology_key = (
        datetime.combine(submitted_date, time.min)
        if submitted_date is not None
        else created_at_key
    )

    # The identifier is only a deterministic tie-breaker when the recorded
    # submission and creation chronology are identical; it is not chronology.
    return chronology_key, created_at_key, str(approval.id)


def _is_deliverable_complete(deliverable: Deliverable) -> bool:
    if is_complete_status(deliverable.status):
        return True

    revision = latest_revision(deliverable)
    if revision is None:
        return False

    approval = latest_approval(revision)
    if approval is None:
        return False

    return is_complete_status(approval.status)


def calculate_package_readiness(
    deliverables: list[Deliverable],
    required_on_site_date: date | None,
    *,
    today: date | None = None,
) -> PackageReadinessSummary:
    current_date = today or date.today()

    total_deliverables = len(deliverables)
    complete_deliverables = 0
    overdue_issue_count = 0
    overdue_approval_count = 0
    missing_revision_count = 0
    pending_approval_count = 0

    for deliverable in deliverables:
        is_complete = _is_deliverable_complete(deliverable)

        if is_complete:
            complete_deliverables += 1

        if (
            not is_complete
            and deliverable.planned_issue_date is not None
            and deliverable.planned_issue_date < current_date
        ):
            overdue_issue_count += 1

        if (
            not is_complete
            and deliverable.required_approval_date is not None
            and deliverable.required_approval_date < current_date
        ):
            overdue_approval_count += 1

        revision = latest_revision(deliverable)
        if revision is None:
            missing_revision_count += 1
            continue

        approval = latest_approval(revision)
        if approval is None or not is_complete_status(approval.status):
            pending_approval_count += 1

    incomplete_deliverables = total_deliverables - complete_deliverables

    if required_on_site_date is None or total_deliverables == 0:
        return PackageReadinessSummary(
            key="setup_required",
            label="Setup required",
            description=(
                "Add a required-on-site date and deliverables to assess readiness."
            ),
            css_class="badge-muted",
            total_deliverables=total_deliverables,
            complete_deliverables=complete_deliverables,
            overdue_issue_count=overdue_issue_count,
            overdue_approval_count=overdue_approval_count,
            missing_revision_count=missing_revision_count,
            pending_approval_count=pending_approval_count,
        )

    if incomplete_deliverables == 0:
        return PackageReadinessSummary(
            key="ready",
            label="Ready",
            description="All recorded deliverables are complete or accepted.",
            css_class="badge-success",
            total_deliverables=total_deliverables,
            complete_deliverables=complete_deliverables,
            overdue_issue_count=overdue_issue_count,
            overdue_approval_count=overdue_approval_count,
            missing_revision_count=missing_revision_count,
            pending_approval_count=pending_approval_count,
        )

    if required_on_site_date < current_date:
        return PackageReadinessSummary(
            key="critical",
            label="Critical",
            description="The package is required on site and remains incomplete.",
            css_class="badge-critical",
            total_deliverables=total_deliverables,
            complete_deliverables=complete_deliverables,
            overdue_issue_count=overdue_issue_count,
            overdue_approval_count=overdue_approval_count,
            missing_revision_count=missing_revision_count,
            pending_approval_count=pending_approval_count,
        )

    if overdue_issue_count > 0 or overdue_approval_count > 0:
        return PackageReadinessSummary(
            key="at_risk",
            label="At risk",
            description="One or more design or approval dates are overdue.",
            css_class="badge-warning",
            total_deliverables=total_deliverables,
            complete_deliverables=complete_deliverables,
            overdue_issue_count=overdue_issue_count,
            overdue_approval_count=overdue_approval_count,
            missing_revision_count=missing_revision_count,
            pending_approval_count=pending_approval_count,
        )

    days_to_site = (required_on_site_date - current_date).days
    if days_to_site <= 14:
        return PackageReadinessSummary(
            key="approaching",
            label="Approaching",
            description=(
                "The required-on-site date is within 14 days and work remains."
            ),
            css_class="badge-warning",
            total_deliverables=total_deliverables,
            complete_deliverables=complete_deliverables,
            overdue_issue_count=overdue_issue_count,
            overdue_approval_count=overdue_approval_count,
            missing_revision_count=missing_revision_count,
            pending_approval_count=pending_approval_count,
        )

    return PackageReadinessSummary(
        key="in_progress",
        label="In progress",
        description="No overdue recorded dates, but the package is not yet ready.",
        css_class="badge-muted",
        total_deliverables=total_deliverables,
        complete_deliverables=complete_deliverables,
        overdue_issue_count=overdue_issue_count,
        overdue_approval_count=overdue_approval_count,
        missing_revision_count=missing_revision_count,
        pending_approval_count=pending_approval_count,
    )
