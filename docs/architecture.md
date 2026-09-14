# Call-Off Architecture

## Purpose

Call-Off is a multi-tenant construction delivery system for specialist
subcontractors. It translates the project Programme into understandable delivery
requirements and should ultimately show whether delivery is ahead of, aligned
with, or behind that Programme.

It is not a general ERP or a replacement for Primavera P6 or Microsoft Project.

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

## Operational domain model

Organisation
→ Project
→ Programme
→ Package Identification
→ Delivery Packages
→ Configurable Delivery Workstreams
→ Readiness / Delivery
→ Site Progress
→ Programme Position

### Ownership

- **Organisation** owns tenant configuration, including future package
  classification and workstream choices.
- **Project** owns project context. New Projects receive one Programme container;
  legacy Projects may have none until their first explicit Programme write.
- **Programme** owns revisions, hierarchical activities, dates, dependencies,
  calendars, imports and baselines. Its current revision is the schedule record.
- **Package** is currently persisted as `WorkPackage`. It describes what is being
  delivered, where, and when, and translates Programme requirements into an
  operational unit.
- **Workstreams** will be organisation-configurable Package functions. They are
  not yet represented by a generic workflow model.
- **Deliverable → Deliverable Revision → Approval** is the current technical/
  design-information capability and should later sit within the relevant enabled
  workstream rather than define all Package readiness.
- **Programme Position** will be derived from Programme requirements and recorded
  operational progress. Current health signals are provisional and are not a
  true ahead/on/behind calculation.

### Programme and Package relationship

The intended relationship is many-to-many:

- one Programme Activity may inform multiple Packages;
- one Package may be informed by multiple Programme Activities.

The current nullable `ProgrammeActivity.work_package_id` supports only the second
case. It is a known transitional constraint, not the target architecture. Replace
it with an explicit neutral association only after deciding whether links persist
across Programme revisions and what purpose/source metadata the association needs.
Do not add new behaviour that assumes one Activity has only one Package.

### Date authority

Programme Activity dates are the authoritative schedule record in the current
Programme revision. Existing Project and Package dates remain stored for backward
compatibility as manually recorded context or operational commitments. They are
not currently derived, synchronised, or formal overrides.

Until provenance and override rules are decided:

- do not delete or silently synchronise those fields;
- do not present duplicate date entry as universally required;
- do not claim Package dates are Programme-derived;
- make calculations explicit about which date source they use.

### Current versus future Programme capability

Manual hierarchical activity editing and the Gantt-style workspace are active.
Models for dependencies, imports, baselines and calendars are useful Programme
foundations but do not yet have complete operational workflows. Preserve them;
do not describe their mere persistence as finished functionality.

A new Project creates the Programme container but does not choose an input method.
The first manual activity creates the initial manual revision; a future import flow
must establish its own revision without first requiring a manual one.

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

### Operational capabilities

Call-Off recognises only `owner`, `project_manager`, and `member` memberships;
unknown roles fail closed.

- All three supported roles may read tenant-scoped operational data.
- `owner` and `project_manager` may create and edit operational data and create
  approval requests.
- `owner` and `project_manager` may record approval responses through the
  separately enforced approval-response capability.
- Only `owner` may permanently delete operational data. This is containment
  pending a future archive and audit workflow.

These capabilities must be enforced consistently by JSON and server-rendered
routes. Template action visibility mirrors the backend policy but is not an
authorisation control.

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
