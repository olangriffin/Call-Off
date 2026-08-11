# Call-Off Agent Setup Update

This package is a drop-in replacement for the repository's agent operating setup.

## Replace

Copy:

- `AGENTS.md` → repository root
- `agents/*.md` → repository `/agents/`

No application code, migrations, tests, or `/docs` files are changed by this package.

## Main changes

- Preserves the existing six-specialist model.
- Keeps the current backend specialist largely unchanged because it is already strongly aligned to the codebase.
- Expands Frontend to cover the actual server-rendered path:
  `app/backend/routes/frontend/` → Jinja context → templates → CSS/JavaScript.
- Expands QA around tenant isolation, rendered behaviour, aggregate accuracy, date boundaries, and dashboard/report testing.
- Expands Security to explicitly cover aggregate/query leakage in dashboards, search, and reporting.
- Expands UX around exception-based construction workflows and operational dashboards.
- Expands Architect around domain hierarchy, server-rendered boundaries, transactions, auditability, and read/query architecture.
- Clarifies that `/agents` files define execution behaviour; they are not evidence of current product behaviour.
- Avoids automatically involving Architect in ordinary work where architecture is not materially changing.

## No new agents

The setup deliberately retains:

1. Architect
2. Backend
3. Frontend
4. QA
5. Security
6. UX

This keeps coordination overhead proportionate to the current Call-Off codebase.
