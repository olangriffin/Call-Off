# Testing Strategy

## Objective
Tests should protect important business behaviour, security boundaries and regression-sensitive workflows.

## Priority order
1. Tenant isolation
2. Authentication and authorisation
3. Core business rules
4. Data integrity
5. Critical user workflows
6. Regression-prone behaviour
7. UI edge states

## Backend tests
Test:
- successful requests
- invalid input
- unauthenticated access
- unauthorised access
- cross-organisation access
- missing resources
- invalid parent-child relationships
- important business rules

## Tenant isolation
Every tenant-scoped feature should include tests proving one organisation cannot access or mutate another organisation's data.

## Regression tests
When fixing a bug:
1. reproduce the bug with a failing test where practical
2. implement the fix
3. confirm the test passes
4. run related tests

## Frontend
Check:
- expected rendering
- empty states
- validation states
- error states
- loading states where applicable
- responsive behaviour
- important interactive behaviour

## Database changes
For schema changes:
- verify migration upgrade
- verify application compatibility
- verify downgrade where practical
- test affected queries and relationships

## Test scope
Prefer targeted tests during development.

Before major changes are considered complete, run the broader relevant suite.

## Failure rule
Do not weaken or delete valid tests simply to make an implementation pass.

If an existing test conflicts with new intended behaviour, document why the expected behaviour changed.