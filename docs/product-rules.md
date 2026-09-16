# Product Rules

## Product objective

Call-Off helps specialist subcontractors translate a project Programme into
understandable delivery requirements and continuously understand whether delivery
is ahead of, aligned with, or behind that Programme.

## Core principles
1. User-first data entry
2. One source of truth
3. Clear ownership
4. Clear deadlines
5. Early warning of delivery risk
6. Minimal administrative overhead
7. Existing tracker data should be importable where practical

## Operational sequence

1. Create the Project context.
2. Import or manually create the Programme.
3. Identify Packages from project scope and Programme requirements.
4. Coordinate each Package through the organisation's enabled workstreams.
5. Record readiness, delivery and later site progress.
6. Explain Package and project position against the Programme.

New Package creation requires the current Programme revision to contain at least
one Activity. Existing legacy Packages remain viewable even where a Programme has
not yet been established, so migration and historical data are not hidden or
deleted.

## Programme import rules

- Microsoft Project XML is the first supported external Programme import format.
- An import must be parsed and previewed before it changes the current Programme.
- Confirming an import creates a new `ProgrammeRevision`; it must never overwrite
  the Activity rows of the previous revision.
- A newly imported revision becomes current only after its Activities and supported
  Dependencies have been created successfully in the same transaction.
- Previous revisions remain available for traceability and future comparison.
- Imported source task IDs are evidence, not durable Package identity.
- The first XML importer should preserve useful schedule structure without trying
  to reproduce all Microsoft Project features. Tasks, hierarchy, dates, duration,
  progress, milestones and supported predecessor links are in scope. Resources,
  costs, assignments, calendars, constraints and baselines are deferred until a
  validated Call-Off workflow needs them.
- Cross-project predecessor links must be reported to the user rather than silently
  converted into internal dependencies.
- Native `.mpp` and configurable XLSX imports are future formats and should
  normalise into the same Programme Revision model rather than create separate
  operational domains.

## Product boundaries

Call-Off is not intended to reproduce every capability of large construction platforms or scheduling tools.

Prioritise workflows that translate Programme requirements into Package delivery
decisions. Do not build a full planning suite, commercial system, procurement
system, or generic workflow builder without a validated operational need.

## Package rules

- Package is the primary operational delivery object. `WorkPackage` is its
  current persistence name.
- A Package describes what is being delivered, where it is being delivered and
  when it is required.
- Area + Scope is a useful default for some organisations, not a universal data
  model. Classification must eventually be organisation-configurable.
- Programme Activity and Package relationships are many-to-many in the target
  model. Do not assume one-to-one or extend the current single-Package activity
  link.

## Package identification rules

- Package identification starts from the current Programme revision and produces
  reviewable candidates before durable Package creation when the interpretation is
  ambiguous.
- The current first-pass Package Identification Preview is deterministic and
  read-only. It groups leaf-activity evidence using the first two Programme
  hierarchy levels as an explainable heuristic, and requires user review before
  any Package is created. The heuristic is not a universal Area + Scope rule.
- A Package is durable project-scoped operational identity; Programme Activities
  are revision-scoped schedule evidence. Do not make Package identity depend on
  one Activity database row or UUID.
- Prefer explainable deterministic evidence first: imported classification,
  external IDs, hierarchy, repeated labels/codes and previously confirmed mapping
  evidence.
- User confirmation is required for ambiguous groupings, split/merge cases,
  unclear classification and one-Activity-to-many-Package interpretation.
- AI/semantic matching may later rank or explain candidates but must not silently
  become authoritative for Package identity, dates or Programme relationships.
- A revised Programme should reconcile against existing Packages and propose link
  changes; it should not create duplicate Packages simply because Activities have
  new database IDs.
- `ProgrammeActivity.work_package_id` is transitional compatibility state. New
  identification functionality must not extend its one-Package assumption.
- The detailed identification contract is maintained in
  `docs/package-identification.md`.

## Workstream rules

- Workstreams are organisation-configurable functions supporting Package
  delivery, such as Design, Commercial, Procurement, Logistics, HSEQ, Quality or
  Site Delivery.
- Do not hard-code a universal Design → Commercial → Procurement → Site flow.
- Configurability must use strong defaults and remain operationally clear; do not
  create a generic workflow-builder experience.
- Existing Deliverable → Revision → Approval behaviour is retained as the
  current technical/design-information capability.

## Programme-position rules

- Risk should ultimately express delivery position against Programme
  requirements: ahead, on programme, approaching risk, or off programme/late.
- Current date and readiness checks are control signals only. Do not label them
  as calculated Programme position until activity/package linkage, progress and
  date authority support that conclusion.
- Do not infer health from an unimplemented workstream or fabricate an
  "Incomplete" status for it.

## UX rules
Users should not need to understand the underlying data model.

Prefer:
- obvious actions
- sensible defaults
- minimal required fields
- clear status language
- useful dashboards
- exception-based reporting

Avoid:
- unnecessary configuration
- duplicate data entry
- deeply nested workflows
- features without a validated user problem

## Feature decision rule
Before implementing a new feature, determine:
- Which user problem it solves
- Which role uses it
- What decision or action it improves
- Whether existing functionality already solves the problem

If these cannot be identified, do not expand the product unnecessarily.
