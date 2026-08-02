from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.models.package.approval import Approval
from app.backend.models.package.revision import DeliverableRevision
from app.backend.schemas.approval import (
    ApprovalCreate,
    ApprovalUpdate,
)


class ApprovalServiceError(Exception):
    """Base exception for approval service errors."""


class InvalidApprovalUpdateError(ApprovalServiceError):
    """Raised when an approval update is invalid."""


def create_approval(
    database: Session,
    revision: DeliverableRevision,
    approval_data: ApprovalCreate,
) -> Approval:
    approval = Approval(
        revision_id=revision.id,
        **approval_data.model_dump(),
    )

    database.add(approval)
    database.commit()
    database.refresh(approval)

    return approval


def list_approvals(
    database: Session,
    revision_id: uuid.UUID,
    *,
    offset: int = 0,
    limit: int = 100,
) -> list[Approval]:
    statement = (
        select(Approval)
        .where(
            Approval.revision_id == revision_id,
        )
        .order_by(
            Approval.created_at,
            Approval.id,
        )
        .offset(offset)
        .limit(limit)
    )

    return list(database.scalars(statement).all())


def get_approval(
    database: Session,
    approval_id: uuid.UUID,
    revision_id: uuid.UUID,
) -> Approval | None:
    statement = select(Approval).where(
        Approval.id == approval_id,
        Approval.revision_id == revision_id,
    )

    return database.scalar(statement)


def update_approval(
    database: Session,
    approval: Approval,
    approval_data: ApprovalUpdate,
) -> Approval:
    update_values = approval_data.model_dump(
        exclude_unset=True,
    )

    required_fields = {
        "approval_stage",
        "status",
    }

    for field_name in required_fields:
        if (
            field_name in update_values
            and update_values[field_name] is None
        ):
            raise InvalidApprovalUpdateError(
                f"{field_name} cannot be null."
            )

    submitted_date = update_values.get(
        "submitted_date",
        approval.submitted_date,
    )
    response_due_date = update_values.get(
        "response_due_date",
        approval.response_due_date,
    )
    response_received_date = update_values.get(
        "response_received_date",
        approval.response_received_date,
    )

    if (
        submitted_date is not None
        and response_due_date is not None
        and response_due_date < submitted_date
    ):
        raise InvalidApprovalUpdateError(
            "response_due_date cannot be earlier "
            "than submitted_date."
        )

    if (
        submitted_date is not None
        and response_received_date is not None
        and response_received_date < submitted_date
    ):
        raise InvalidApprovalUpdateError(
            "response_received_date cannot be earlier "
            "than submitted_date."
        )

    for field_name, value in update_values.items():
        setattr(approval, field_name, value)

    database.commit()
    database.refresh(approval)

    return approval


def delete_approval(
    database: Session,
    approval: Approval,
) -> None:
    database.delete(approval)
    database.commit()
