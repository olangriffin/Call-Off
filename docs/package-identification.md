# Programme to Package Identification

## Purpose

This document defines the current architectural contract for turning a Project
Programme into operational Packages. It is intentionally conservative: it defines
the boundary and review workflow without implementing AI matching, configurable
workstreams, backwards scheduling, or a new persistence model.

The product objective remains:

> Translate the project Programme into understandable delivery requirements and
> continuously explain whether delivery is ahead of, aligned with, or behind that
> Programme.

## Current Programme Model

The current repository represents Programme information as follows:

- A `Project` owns a `Programme` container. New Projects create that container
  without choosing whether the first revision will be manual or imported.
- `ProgrammeRevision` is revision-scoped and records revision code, source type,
  source filename, status, revision date and whether it is current.
- `ProgrammeActivity` belongs to one revision and currently records:
  - activity code and name;
  - activity type;
  - optional external ID;
  - parent/child hierarchy and derived summary state;
  - planned start and finish;
  - duration;
  - percent complete and status;
  - milestone state;
  - notes;
  - optional calendar;
  - dependencies through the dependency model.
- `ProgrammeImport` can retain source details, mapping configuration and
  validation issues, but a complete import workflow is not yet implemented.
- Baseline, calendar and dependency models are useful Programme foundations but
  must not be treated as complete workflows merely because persistence exists.
- The Gantt-style workspace renders the current revision hierarchy and dates.
- `ProgrammeActivity.work_package_id` is a transitional compatibility link. It
  can link one Activity to at most one `WorkPackage`; it is not the target
  Package-identification relationship.

The information available today that may help identify Packages is therefore
primarily the activity hierarchy, codes, names, external IDs, types, dates,
repeated structure and imported mapping metadata where present. There are no
canonical first-class Area, Zone, Scope, Trade, System or Discipline fields today.

## Package Definition

A Package is the stable, project-scoped operational unit used to coordinate a
meaningful piece of delivery. It is persisted today as `WorkPackage`.

A confirmed Package must answer, at a useful operational level:

- **WHAT** is being delivered;
- **WHERE** it is being delivered; and
- **WHEN** the Programme requires it.

A Package is not inherently:

- one Programme Activity;
- one WBS node;
- Area + Scope;
- a Design package;
- a Procurement package; or
- a fixed sequence of Design → Commercial → Procurement → Site.

Those may be valid structures for a particular organisation or project, but they
are not universal product rules.

### Domain ownership

**Programme Activity** owns revision-specific schedule evidence: activity identity
within that revision, hierarchy, planned dates, dependencies and progress fields.

**Package** owns durable operational identity: project, code, name, status,
description and organisation-relevant classification. A Package should be able to
survive Programme revisions even when individual activities are renamed, split,
merged or replaced.

**Programme ↔ Package association** should eventually express which revision-
scoped activities inform a Package. The association is evidence linking schedule
requirements to the durable operational object; it must not make the Package's
identity depend on one Activity database ID.

**Organisation configuration** will eventually own sensible Package
classification defaults and enabled workstreams. It should not become a generic
no-code schema builder.

### Date ownership

Programme Activity dates are the authoritative schedule record for the current
Programme revision.

Existing `WorkPackage.planned_start`, `planned_finish` and
`required_on_site_date` remain manual context/commitment fields in the current
build. They are not currently derived or synchronised. Future derivation must be
explicit about source, meaning and override behaviour.

## Identification Signals

### Available now

The current model can expose these signals without schema changes:

- Programme hierarchy and full parent path;
- summary versus leaf activities;
- activity names;
- activity codes;
- imported `external_id` where present;
- activity type and milestone state;
- planned dates and duration;
- repeated naming/code patterns;
- dependencies;
- source/revision information;
- import mapping configuration where populated; and
- the existing transitional `work_package_id` as legacy evidence only.

### Suitable for deterministic identification

Deterministic logic may use strong, explainable evidence such as:

- explicit imported classification metadata;
- stable external identifiers from the source Programme;
- repeated hierarchy structures;
- exact repeated labels or structured code prefixes;
- explicit user-selected hierarchy levels/classification dimensions; and
- previously confirmed mappings where the same durable source identity survives
  into a new revision.

A deterministic rule must be explainable to the user. A rule should produce a
candidate, not silently create a Package when the interpretation is ambiguous.

### Requires user confirmation

User review is required where evidence does not uniquely determine the Package,
including:

- a name that contains several possible location/scope dimensions;
- different projects using different hierarchy depths;
- summary nodes that mix several operational scopes;
- one Activity contributing to multiple Packages;
- multiple Activities that may represent one Package;
- activity splits/merges between revisions;
- deciding which Programme requirement drives a Package's required-on-site or
  other operational date; and
- ambiguous classification terminology.

### Future AI assistance

AI or semantic matching may later help with:

- interpreting inconsistent activity descriptions;
- normalising equivalent location/scope terminology;
- suggesting likely Package groupings from naming and hierarchy context;
- reconciling renamed activities between revisions; and
- ranking ambiguous candidates for review.

AI must remain advisory. It should produce candidates with evidence/confidence for
review rather than becoming the authoritative source of Package identity or dates.

## Proposed Identification Workflow

The intended user/system flow is:

1. **Establish Programme** — import or manually create the Programme.
2. **View Programme** — confirm the current revision, hierarchy and dates are
   usable before deriving operational structure.
3. **Analyse structure** — Call-Off evaluates deterministic identification
   signals from the current revision.
4. **Propose candidates** — Call-Off presents candidate Packages and the Activity
   evidence behind each suggestion. Candidates are not yet confirmed Packages.
5. **Review ambiguity** — the user can rename, regroup, split, merge or reject
   candidates and resolve Activities that cannot be classified safely.
6. **Confirm Packages** — confirmation creates or updates durable `WorkPackage`
   records and establishes the appropriate Programme Activity links.
7. **Operate the Package** — enabled workstreams, readiness and delivery tracking
   attach to the confirmed Package rather than to a transient candidate.
8. **Reconcile revisions** — a revised Programme is compared with existing
   Packages and existing confirmed mapping evidence; Call-Off proposes link
   changes rather than creating duplicate Packages automatically.

Manual Package creation remains a valid fallback/legacy path, but the desired
future default is Programme-led assisted identification.

## Relationship Model

The target cardinality is many-to-many:

- one Programme Activity may inform multiple Packages;
- one Package may be informed by multiple Programme Activities.

The durable identity boundary is:

```text
Project
├── Package (stable operational identity)
└── Programme
    └── Revision
        └── Activity (revision-scoped schedule identity)
```

A future neutral association should link `WorkPackage` and `ProgrammeActivity`.
Do not add that migration until the minimum useful association semantics are
validated from real Programme samples.

### Association metadata

The minimum association always needs:

- Package identity; and
- Programme Activity identity.

Revision context is already available through the Activity's
`programme_revision_id`; duplicating it on the association is unnecessary unless a
future query or integrity requirement proves otherwise.

Potential metadata should only be added when the workflow validates its need:

- relationship purpose (for example, which Activity drives a particular Package
  requirement);
- mapping source (manual, deterministic rule, import or assisted suggestion);
- confirmation/audit information.

Confidence and explanation are primarily properties of an unconfirmed candidate
suggestion. They should not be added to the permanent association merely because
future AI may exist.

### Programme revision behaviour

Package identity persists independently of Programme revisions.

When a new revision arrives:

1. retain the old revision and its Activity links for traceability;
2. analyse the new revision against existing Packages;
3. prefer durable source evidence such as external IDs when available;
4. then use deterministic code/hierarchy/name evidence;
5. present uncertain split/merge/rename cases for review;
6. establish links to Activities in the new revision after confirmation; and
7. never assume an Activity database UUID or row survives between revisions.

The current `ProgrammeActivity.work_package_id` cannot represent this target
relationship and should eventually be removed after a neutral association has
been introduced and legacy data migrated safely.

## Existing WorkPackage Review

| Field | Classification | Direction |
| --- | --- | --- |
| `project_id` | KEEP | Package remains project-scoped. |
| `code` | KEEP | Stable human/business reference within a project. |
| `name` | KEEP | Stable operational label; may be proposed then user-confirmed. |
| `package_type` | LEGACY / REVIEW | Useful current classification placeholder, but one free-text field is unlikely to represent all organisation classification needs. Do not remove yet. |
| `description` | KEEP | Optional operational context. |
| `status` | KEEP | Package lifecycle state is distinct from Programme Activity status. |
| `planned_start` | DERIVED EVENTUALLY | Manual context today; likely informed by Programme links once date semantics are validated. |
| `planned_finish` | DERIVED EVENTUALLY | Manual context today; likely informed by Programme links once date semantics are validated. |
| `required_on_site_date` | DERIVED EVENTUALLY | Important operational requirement, but the driving Activity/date and override rules are not yet defined. |

`ProgrammeActivity.work_package_id` is not a `WorkPackage` field, but its lifecycle
classification is **REMOVE LATER** after a many-to-many replacement and safe data
migration exist.

## Changes Made

This architecture pass intentionally makes no database migration and no automatic
Package creation.

Repository alignment for this pass should be limited to:

- making this document the detailed Programme → Package identification contract;
- referencing the contract from the core architecture/product rules;
- marking the current one-Package Activity link as transitional in code/API
  documentation; and
- preventing future work from treating Area + Scope or the current
  `work_package_id` column as universal product truth.

## Deferred Decisions

These decisions require real Programme samples and operational validation before
being hard-coded:

- the best default Package classification dimensions across target sectors;
- whether candidate suggestions need temporary persistence or can initially be a
  read model;
- which Programme Activity or milestone drives each Package date requirement;
- Package date derivation, override and provenance rules;
- whether permanent Activity↔Package links need a relationship-purpose field;
- confidence thresholds for deterministic or AI-assisted suggestions;
- exact split/merge behaviour when Programme revisions restructure activities;
- the smallest organisation-level classification configuration that remains easy
  to use; and
- the future workstream configuration model.

## Recommended Next Build

Build one narrow **Package Identification Preview** against the current Programme
revision.

The first version should be read-only and deterministic. It should expose the
current Activity hierarchy plus the evidence Call-Off could use to form candidate
Packages, and present candidate groupings for review without creating Packages or
adding a new database relationship.

That build should validate the identification signals and review UX using real
Programme samples. Only after that validation should Call-Off commit to candidate
persistence, a many-to-many migration, or AI-assisted matching.
