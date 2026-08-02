"""harden early access applications

Revision ID: c4e21d8a3f70
Revises: 19a6d640be9d
Create Date: 2026-08-02 01:20:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e21d8a3f70"
down_revision: str | Sequence[str] | None = "19a6d640be9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CONSTRAINTS = (
    (
        "ck_early_access_full_name_length",
        "length(trim(full_name)) BETWEEN 1 AND 200",
    ),
    (
        "ck_early_access_work_email_normalized",
        "length(work_email) BETWEEN 3 AND 320 "
        "AND work_email = lower(trim(work_email))",
    ),
    (
        "ck_early_access_company_name_length",
        "length(trim(company_name)) BETWEEN 1 AND 200",
    ),
    (
        "ck_early_access_job_title_length",
        "length(trim(job_title)) BETWEEN 1 AND 160",
    ),
    (
        "ck_early_access_trade_length",
        "length(trim(subcontractor_type)) BETWEEN 1 AND 160",
    ),
    (
        "ck_early_access_company_size",
        "company_size IN ('1-10', '11-50', '51-150', '151-500', '500+')",
    ),
    (
        "ck_early_access_active_projects",
        "active_projects IN ('1-3', '4-10', '11-25', '26-50', '50+')",
    ),
    (
        "ck_early_access_current_tools_length",
        "length(trim(current_tools)) BETWEEN 1 AND 2000",
    ),
    (
        "ck_early_access_challenge_length",
        "length(trim(biggest_delivery_challenge)) BETWEEN 1 AND 4000",
    ),
    (
        "ck_early_access_interest_level",
        "interest_level IN ('early_access', 'pilot_customer', 'design_partner')",
    ),
    (
        "ck_early_access_additional_information_length",
        "additional_information IS NULL OR length(additional_information) <= 4000",
    ),
    (
        "ck_early_access_ip_hash_length",
        "length(ip_address_hash) = 64",
    ),
    (
        "ck_early_access_user_agent_length",
        "user_agent IS NULL OR length(user_agent) <= 500",
    ),
)


def upgrade() -> None:
    for name, condition in CONSTRAINTS:
        op.create_check_constraint(
            name,
            "early_access_applications",
            condition,
        )


def downgrade() -> None:
    for name, _condition in reversed(CONSTRAINTS):
        op.drop_constraint(
            name,
            "early_access_applications",
            type_="check",
        )
