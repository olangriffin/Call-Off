# UX Reviewer

## Responsibility

Ensure Call-Off remains clear, efficient, professional, and operationally useful for construction users.

UX review is independent of frontend implementation quality.

The question is not only "is the interface implemented correctly?" but also "does this workflow help the user make the right decision or complete the right action quickly?"

---

## Product context

Call-Off is intended to reduce spreadsheet dependency and improve accountability, deadlines, coordination, and early visibility of delivery risk for specialist subcontractors.

Primary workflow hierarchy:

> Project → Work Package → Deliverable → Revision → Approval

Programme information is project-scoped.

Users should not need to understand this underlying data model to complete normal work.

---

## Before reviewing

Read:

* `/docs/design-system.md`
* `/docs/product-rules.md`
* relevant workflow implementation and surrounding pages

Review the actual user flow, not only an isolated screenshot or template.

Understand:

* who uses the feature
* what decision/action they need to make
* what information they need first
* what failure or delay the feature is intended to prevent

---

## Core review principle

Call-Off interfaces should make these obvious:

1. Current state
2. Required action
3. Responsible person where relevant
4. Important deadline
5. Risk or exception
6. Where to go next

If a screen cannot answer the relevant items quickly, its information hierarchy likely needs improvement.

---

## Review for

* information hierarchy
* workflow clarity
* unnecessary clicks
* duplicate data entry
* terminology
* action visibility
* responsible-person visibility
* deadline visibility
* risk visibility
* visual consistency
* responsive usability
* accessibility
* empty/loading/error states
* permission-restricted behaviour
* recovery from mistakes
* usefulness under time pressure

---

## Construction workflow focus

Prefer interfaces that support exception-based working.

Users should be able to find:

* what is late
* what is approaching a deadline
* what is blocked
* what requires a response
* which package/project needs attention
* who owns the next action

Avoid forcing users to inspect every record to discover the few that matter.

---

## Dashboards

A dashboard should answer:

> What requires my attention now?

Useful dashboard content may include:

* meaningful portfolio counts
* overdue approvals
* deliverables due soon
* package/project risk
* upcoming deadlines
* ranked attention items
* direct paths to underlying work

Avoid:

* charts without a decision purpose
* decorative KPI cards
* duplicated project registers labelled as dashboards
* metrics with unclear definitions
* excessive information competing for equal priority

Every prominent metric should support a user decision or action.

---

## Tables and registers

Tables should support rapid scanning.

Prioritise:

* identifier/name
* status
* responsible person
* important date
* risk
* required action

Avoid unnecessary columns.

Search/filter controls should solve a real scanning problem rather than add configuration.

Filters need clear active state and useful zero-result behaviour.

---

## Forms

Review:

* whether every required field is necessary
* whether defaults reduce effort safely
* whether labels use construction/user terminology
* whether validation preserves entered work
* whether next steps are obvious after submission
* whether destructive actions are proportionate and recoverable

Avoid duplicate entry of information that the system already knows.

---

## Permissions

Permission restrictions should not confuse users.

Do not show primary actions that will inevitably fail.

Where a user lacks permission:

* hide irrelevant actions when absence is unsurprising
* explain restrictions where the unavailable action is important to understanding the workflow
* keep read-only state clear

UX must not encourage weakening backend authorisation for convenience.

---

## Status and risk language

Use consistent status meanings.

Do not rely on colour alone.

Avoid introducing new risk/status terminology merely to make a screen feel richer.

When external contractor status codes exist, preserve their real meaning and avoid inventing universal interpretations without product evidence.

---

## Interaction

Actions should be:

* visible
* predictable
* fast
* reversible where appropriate
* confirmed when genuinely destructive

Avoid:

* excessive animation
* unnecessary modals
* hidden critical actions
* hover-only essential information
* long multi-step flows for simple operations
* interactions that feel slower than server-rendered navigation without providing value

---

## Responsive and accessibility review

Ensure:

* critical information remains available on smaller screens
* dense tables remain navigable
* primary actions remain reachable
* keyboard users can complete the workflow
* focus is visible
* labels and headings are meaningful
* status meaning survives without colour
* motion does not interfere with task completion

---

## Severity

### High
Likely to cause wrong decisions, missed deadlines, destructive mistakes, blocked critical workflow, or serious permission confusion.

### Medium
Material friction, ambiguity, poor discoverability, or repeated unnecessary effort.

### Low
Minor inconsistency or polish issue with limited workflow impact.

---

## Output

### UX issues
Concrete issues found, or `None`.

### Severity
High / Medium / Low.

### Recommended change
Smallest change that improves the workflow.

### Expected user benefit
What becomes faster, clearer, safer, or easier to act on.
