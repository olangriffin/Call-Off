# Call-Off Agent Operating Model

## Objective
Work as an engineering team, not as a single general-purpose coding agent.

Before implementing a task:
1. Understand the requested outcome.
2. Inspect the relevant existing implementation.
3. Read the relevant project documentation in `/docs`.
4. Select the specialist roles required from `/agents`.
5. Delegate independent work to subagents where this will improve speed or verification.
6. Implement the smallest coherent solution.
7. Verify the completed behaviour.
8. Report the result concisely.

## Project context

Read only the documentation relevant to the task:

- Architecture → `/docs/architecture.md`
- Product/business behaviour → `/docs/product-rules.md`
- Coding conventions → `/docs/coding-standards.md`
- UI/UX → `/docs/design-system.md`
- Testing → `/docs/testing.md`

Do not repeatedly rediscover information already documented.

## Specialist roles

Use the following specialist instructions:

- System design / architectural changes → `/agents/architect.md`
- Backend / API / database → `/agents/backend.md`
- Frontend / templates / CSS / JavaScript → `/agents/frontend.md`
- Testing / regression verification → `/agents/qa.md`
- Authentication / authorisation / tenant security → `/agents/security.md`
- UX / usability / interface review → `/agents/ux.md`

## Delegation

Use subagents where tasks can be performed independently.

Examples:

### Full-stack feature
Architect
→ Backend + Frontend in parallel where possible
→ QA
→ Security if security boundaries are affected
→ UX if user-facing behaviour changes

### Backend change
Backend
→ QA
→ Security when authentication, authorisation, organisations or tenant data are involved

### Frontend change
Frontend
→ QA
→ UX

### Bug
QA reproduces/identifies cause
→ appropriate implementation specialist
→ QA verifies regression

### Security issue
Security identifies and scopes issue
→ implementation specialist fixes
→ Security + QA verify

Do not delegate unnecessarily small tasks.

## Verification

Never consider implementation complete merely because code was written.

Run applicable:
- targeted tests
- broader regression tests where justified
- syntax/type/lint checks available in the repository
- database migration checks where applicable
- browser/UI verification for user-facing changes

If verification cannot be run, explicitly state why.

## Engineering rules

- Preserve multi-tenant isolation.
- Never trust client-supplied organisation ownership.
- Reuse existing architecture and UI patterns.
- Avoid unnecessary dependencies.
- Avoid unrelated refactoring.
- Do not weaken tests to make code pass.
- Do not silently change product behaviour.
- Prefer implementation over lengthy analysis once the approach is sufficiently clear.

## Completion format

Return:

### Completed
What was implemented.

### Changed
Files/components changed.

### Verified
Tests and checks performed.

### Remaining
Only genuine unresolved risks, assumptions or follow-up work.

## Repository scope

For engineering tasks, treat the current repository as the primary source of truth.

Do not inspect external memory systems, SecondBrain directories, unrelated repositories, or personal notes unless:
- explicitly requested by the user, or
- required information is unavailable in the repository.

Use this order:
1. Current repository code
2. `/docs`
3. `/agents`
4. Repository tests
5. Git history where relevant
6. External context only when necessary