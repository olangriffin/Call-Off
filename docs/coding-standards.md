# Coding Standards

## General
- Prefer simple, explicit code over clever abstractions.
- Reuse existing patterns before introducing new ones.
- Keep changes scoped to the requested behaviour.
- Avoid unrelated refactors during feature work.
- Preserve backward compatibility unless a change explicitly requires otherwise.

## Python
- Use clear type annotations where practical.
- Keep functions focused and reasonably small.
- Prefer explicit exceptions and validation.
- Avoid duplicated business logic.
- Keep route handlers thin where practical.

## FastAPI
- Validate input through schemas.
- Derive tenant context from authenticated access.
- Do not trust client-supplied organisation ownership.
- Return appropriate HTTP status codes.
- Keep endpoint behaviour predictable.

## SQLAlchemy
- Keep relationships explicit.
- Avoid unnecessary queries.
- Validate parent-child ownership before mutating nested resources.
- Use migrations for schema changes.

## Database
- PostgreSQL is the source of truth.
- Schema changes require Alembic migrations.
- Migrations must be reversible where practical.
- Avoid destructive migrations without explicit review.

## Frontend
- Prefer existing Jinja patterns.
- Reuse existing CSS and components.
- Avoid introducing frameworks or dependencies without clear benefit.
- Keep JavaScript focused on behaviour that cannot be handled cleanly server-side.

## Naming
- Use descriptive names.
- Avoid unexplained abbreviations.
- Keep domain terminology consistent across backend, frontend and database layers.

## Comments
Comments should explain why, not restate what the code already says.

## Dependencies
Before adding a dependency:
- confirm existing tools cannot solve the problem
- justify the dependency
- consider maintenance and security cost