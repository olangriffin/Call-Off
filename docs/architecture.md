# Call-Off Architecture

## Purpose
Call-Off is a multi-tenant pre-construction ERP for specialist subcontractors.

Core domains:
- Organisations
- Projects
- Work Packages
- Deliverables
- Deliverable Revisions
- Approvals
- Programme Activities
- Dependencies

## Stack
Backend:
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL

Frontend:
- Jinja templates
- CSS
- JavaScript where required

Hosting:
- Render
- PostgreSQL database

## Domain hierarchy
Organisation
→ Project
→ Work Package
→ Deliverable
→ Deliverable Revision
→ Approval

Programme:
Project
→ Programme Activity
→ Dependencies / Baselines / Calendar

## Multi-tenancy
Every operational request must derive organisation access from authenticated membership.

Never trust a client-supplied `organization_id`.

Tenant-scoped resources must only be accessible where the authenticated user has valid access to the owning organisation.

## Backend conventions
- Routes should remain thin where practical.
- Business rules should not be duplicated across endpoints.
- Parent-child relationships must be validated.
- Prefer explicit schemas over unstructured dictionaries.
- Database changes require Alembic migrations.
- Avoid breaking existing API behaviour without explicit justification.

## Security boundary
Organisation membership is the primary tenant boundary.

`CurrentOrganisationAccess` should be used where appropriate to derive tenant context.

Inactive or revoked memberships must not grant access.

### Project creation capability

Project creation is allowed for organisation `owner` and `project_manager`
memberships. A `member` may view tenant-scoped project information but may not
create a project.

This rule applies consistently to server-rendered HTML routes, JSON API routes,
and the visibility of project-creation actions in the interface. Tenant
ownership must still be derived from the authenticated membership.

## Frontend architecture
Server-rendered Jinja templates are the default.

Avoid introducing frontend frameworks unless there is a clear architectural reason.

Reuse existing:
- layouts
- partials
- CSS patterns
- components
- navigation structures

before creating new ones.
