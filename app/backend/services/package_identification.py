from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from app.backend.models.programme.programme_activity import ProgrammeActivity


@dataclass(frozen=True, slots=True)
class PackageIdentificationEvidence:
    activity_id: uuid.UUID
    activity_code: str
    activity_name: str
    hierarchy_path: str
    start_date: date | None
    finish_date: date | None
    work_package_code: str | None


@dataclass(frozen=True, slots=True)
class PackageIdentificationCandidate:
    anchor_activity_id: uuid.UUID
    proposed_name: str
    what_label: str
    where_label: str | None
    start_date: date | None
    finish_date: date | None
    evidence: tuple[PackageIdentificationEvidence, ...]
    evidence_strength: str
    rationale: str
    linked_package_codes: tuple[str, ...]
    fully_linked: bool
    partially_linked: bool

    @property
    def activity_count(self) -> int:
        return len(self.evidence)


@dataclass(frozen=True, slots=True)
class PackageIdentificationPreview:
    candidates: tuple[PackageIdentificationCandidate, ...]
    source_activity_count: int
    candidate_activity_count: int
    linked_activity_count: int


def _as_date(value: date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def _activity_window(activity: ProgrammeActivity) -> tuple[date | None, date | None]:
    start = _as_date(activity.planned_start)
    finish = _as_date(activity.planned_finish)

    # A milestone or partially scheduled activity may legitimately provide only
    # one date. Use that point for both sides of the preview window rather than
    # inventing duration.
    return start or finish, finish or start


def _path_to_activity(
    activity: ProgrammeActivity,
    activity_by_id: dict[uuid.UUID, ProgrammeActivity],
) -> list[ProgrammeActivity]:
    path: list[ProgrammeActivity] = []
    seen: set[uuid.UUID] = set()
    current: ProgrammeActivity | None = activity

    while current is not None and current.id not in seen:
        seen.add(current.id)
        path.append(current)
        current = (
            activity_by_id.get(current.parent_activity_id)
            if current.parent_activity_id is not None
            else None
        )

    path.reverse()
    return path


def _candidate_anchor(
    path: list[ProgrammeActivity],
    wrapper_root_id: uuid.UUID | None,
) -> tuple[ProgrammeActivity, ProgrammeActivity | None]:
    meaningful_path = path
    if wrapper_root_id is not None and path and path[0].id == wrapper_root_id:
        meaningful_path = path[1:]

    if not meaningful_path:
        meaningful_path = path

    # The first two meaningful hierarchy levels are used only as an explainable
    # preview heuristic. When there are at least three levels, the second level
    # becomes the candidate Package and the first level becomes its context.
    # Shallower programmes fall back conservatively to their parent branch or
    # individual activity. This does not establish universal Area + Scope rules.
    if len(meaningful_path) >= 3:
        return meaningful_path[1], meaningful_path[0]
    if len(meaningful_path) == 2:
        return meaningful_path[0], None
    return meaningful_path[0], None


def build_package_identification_preview(
    activities: list[ProgrammeActivity],
) -> PackageIdentificationPreview:
    if not activities:
        return PackageIdentificationPreview(
            candidates=(),
            source_activity_count=0,
            candidate_activity_count=0,
            linked_activity_count=0,
        )

    activity_by_id = {activity.id: activity for activity in activities}
    children_by_parent: dict[uuid.UUID | None, list[ProgrammeActivity]] = {}
    for activity in activities:
        children_by_parent.setdefault(activity.parent_activity_id, []).append(activity)

    root_activities = children_by_parent.get(None, [])
    wrapper_root_id = (
        root_activities[0].id
        if len(root_activities) == 1
        and children_by_parent.get(root_activities[0].id)
        else None
    )

    leaf_activities = [
        activity for activity in activities if not children_by_parent.get(activity.id)
    ]

    grouped: dict[
        uuid.UUID,
        dict[str, object],
    ] = {}

    for activity in leaf_activities:
        path = _path_to_activity(activity, activity_by_id)
        anchor, context = _candidate_anchor(path, wrapper_root_id)

        group = grouped.setdefault(
            anchor.id,
            {
                "anchor": anchor,
                "context": context,
                "evidence": [],
            },
        )

        start_date, finish_date = _activity_window(activity)
        work_package = getattr(activity, "work_package", None)
        work_package_code = getattr(work_package, "code", None)

        evidence = PackageIdentificationEvidence(
            activity_id=activity.id,
            activity_code=activity.activity_code,
            activity_name=activity.name,
            hierarchy_path=" › ".join(node.name for node in path),
            start_date=start_date,
            finish_date=finish_date,
            work_package_code=work_package_code,
        )
        group["evidence"].append(evidence)  # type: ignore[union-attr]

    candidates: list[PackageIdentificationCandidate] = []

    for group in grouped.values():
        anchor = group["anchor"]
        context = group["context"]
        evidence_items = tuple(group["evidence"])

        starts = [item.start_date for item in evidence_items if item.start_date]
        finishes = [item.finish_date for item in evidence_items if item.finish_date]
        linked_codes = tuple(
            sorted(
                {
                    item.work_package_code
                    for item in evidence_items
                    if item.work_package_code
                }
            )
        )
        linked_count = sum(item.work_package_code is not None for item in evidence_items)
        fully_linked = linked_count == len(evidence_items) and bool(evidence_items)
        partially_linked = 0 < linked_count < len(evidence_items)

        where_label = context.name if context is not None else None
        proposed_name = (
            f"{where_label} — {anchor.name}"
            if where_label and where_label != anchor.name
            else anchor.name
        )

        if len(evidence_items) >= 2 and anchor.id != evidence_items[0].activity_id:
            evidence_strength = "Structured hierarchy"
        elif len(evidence_items) >= 2:
            evidence_strength = "Repeated activity grouping"
        else:
            evidence_strength = "Single activity"

        candidates.append(
            PackageIdentificationCandidate(
                anchor_activity_id=anchor.id,
                proposed_name=proposed_name,
                what_label=anchor.name,
                where_label=where_label,
                start_date=min(starts) if starts else None,
                finish_date=max(finishes) if finishes else None,
                evidence=evidence_items,
                evidence_strength=evidence_strength,
                rationale=(
                    "Suggested from the current Programme hierarchy. Review the "
                    "WHAT, WHERE and date window before creating a Package; this "
                    "preview does not establish a universal hierarchy rule."
                ),
                linked_package_codes=linked_codes,
                fully_linked=fully_linked,
                partially_linked=partially_linked,
            )
        )

    candidates.sort(
        key=lambda candidate: (
            candidate.where_label or "",
            candidate.what_label,
            str(candidate.anchor_activity_id),
        )
    )

    candidate_activity_count = sum(candidate.activity_count for candidate in candidates)
    linked_activity_count = sum(
        item.work_package_code is not None
        for candidate in candidates
        for item in candidate.evidence
    )

    return PackageIdentificationPreview(
        candidates=tuple(candidates),
        source_activity_count=len(activities),
        candidate_activity_count=candidate_activity_count,
        linked_activity_count=linked_activity_count,
    )


def find_package_identification_candidate(
    preview: PackageIdentificationPreview,
    anchor_activity_id: uuid.UUID,
) -> PackageIdentificationCandidate | None:
    return next(
        (
            candidate
            for candidate in preview.candidates
            if candidate.anchor_activity_id == anchor_activity_id
        ),
        None,
    )
