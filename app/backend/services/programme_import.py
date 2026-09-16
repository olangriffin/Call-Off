from __future__ import annotations

import hashlib
import re
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backend.models.programme.programme import Programme
from app.backend.models.programme.programme_import import ProgrammeImport
from app.backend.models.project import Project


class ProgrammeImportError(Exception):
    """Base exception for Programme import failures."""


class InvalidProgrammeImportError(ProgrammeImportError):
    """Raised when an import cannot be confirmed safely."""


@dataclass(frozen=True, slots=True)
class ImportedDependency:
    predecessor_uid: str
    successor_uid: str
    dependency_type: str
    lag_minutes: int

    def to_payload(self) -> dict:
        return {
            "predecessor_uid": self.predecessor_uid,
            "successor_uid": self.successor_uid,
            "dependency_type": self.dependency_type,
            "lag_minutes": self.lag_minutes,
        }

    @classmethod
    def from_payload(cls, value: dict) -> ImportedDependency:
        return cls(
            predecessor_uid=str(value["predecessor_uid"]),
            successor_uid=str(value["successor_uid"]),
            dependency_type=str(value["dependency_type"]),
            lag_minutes=int(value.get("lag_minutes", 0)),
        )


@dataclass(frozen=True, slots=True)
class ImportedTask:
    source_uid: str
    activity_code: str
    name: str
    outline_level: int
    parent_uid: str | None
    planned_start: str | None
    planned_finish: str | None
    duration_minutes: int | None
    percent_complete: int
    is_milestone: bool
    is_summary: bool

    @property
    def depth(self) -> int:
        return max(self.outline_level - 1, 0)

    def to_payload(self) -> dict:
        return {
            "source_uid": self.source_uid,
            "activity_code": self.activity_code,
            "name": self.name,
            "outline_level": self.outline_level,
            "parent_uid": self.parent_uid,
            "planned_start": self.planned_start,
            "planned_finish": self.planned_finish,
            "duration_minutes": self.duration_minutes,
            "percent_complete": self.percent_complete,
            "is_milestone": self.is_milestone,
            "is_summary": self.is_summary,
        }

    @classmethod
    def from_payload(cls, value: dict) -> ImportedTask:
        return cls(
            source_uid=str(value["source_uid"]),
            activity_code=str(value["activity_code"]),
            name=str(value["name"]),
            outline_level=int(value.get("outline_level", 1)),
            parent_uid=(str(value["parent_uid"]) if value.get("parent_uid") else None),
            planned_start=value.get("planned_start"),
            planned_finish=value.get("planned_finish"),
            duration_minutes=(
                int(value["duration_minutes"])
                if value.get("duration_minutes") is not None
                else None
            ),
            percent_complete=int(value.get("percent_complete", 0)),
            is_milestone=bool(value.get("is_milestone", False)),
            is_summary=bool(value.get("is_summary", False)),
        )


@dataclass(frozen=True, slots=True)
class ProgrammeImportPreview:
    project_name: str | None
    tasks: tuple[ImportedTask, ...]
    dependencies: tuple[ImportedDependency, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def milestone_count(self) -> int:
        return sum(task.is_milestone for task in self.tasks)

    @property
    def summary_count(self) -> int:
        return sum(task.is_summary for task in self.tasks)

    @property
    def can_confirm(self) -> bool:
        return bool(self.tasks) and not self.errors

    def to_payload(self) -> dict:
        return {
            "project_name": self.project_name,
            "tasks": [task.to_payload() for task in self.tasks],
            "dependencies": [item.to_payload() for item in self.dependencies],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    @classmethod
    def from_payload(cls, value: dict) -> ProgrammeImportPreview:
        return cls(
            project_name=value.get("project_name"),
            tasks=tuple(ImportedTask.from_payload(task) for task in value.get("tasks", [])),
            dependencies=tuple(
                ImportedDependency.from_payload(item)
                for item in value.get("dependencies", [])
            ),
            warnings=tuple(str(item) for item in value.get("warnings", [])),
            errors=tuple(str(item) for item in value.get("errors", [])),
        )


_DURATION_PATTERN = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>[\d.]+)S)?)?$"
)
_DEPENDENCY_TYPES = {"0": "FF", "1": "FS", "2": "SF", "3": "SS"}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element if _local_name(item.tag) == name), None)


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [item for item in element if _local_name(item.tag) == name]


def _text(element: ET.Element, name: str) -> str | None:
    child = _child(element, name)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def _bool_text(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _int_text(value: str | None, default: int = 0) -> int:
    try:
        return int(str(value).strip()) if value is not None else default
    except (TypeError, ValueError):
        return default


def _duration_minutes(value: str | None) -> int | None:
    if not value:
        return None
    match = _DURATION_PATTERN.fullmatch(value.strip())
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0)
    return round(days * 24 * 60 + hours * 60 + minutes + seconds / 60)


def _normalise_datetime(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.isoformat()


def _safe_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    return Path(filename).name[:255]


def parse_ms_project_xml(content: bytes) -> ProgrammeImportPreview:
    warnings: list[str] = []
    errors: list[str] = []

    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        return ProgrammeImportPreview(
            project_name=None,
            tasks=(),
            dependencies=(),
            warnings=(),
            errors=(f"The XML could not be parsed: {error}.",),
        )

    if _local_name(root.tag) != "Project":
        errors.append("The uploaded XML is not a Microsoft Project XML Project document.")

    project_name = _text(root, "Name") or _text(root, "Title")
    tasks_element = _child(root, "Tasks")
    if tasks_element is None:
        errors.append("The XML does not contain a Tasks collection.")
        return ProgrammeImportPreview(
            project_name=project_name,
            tasks=(),
            dependencies=(),
            warnings=tuple(warnings),
            errors=tuple(errors),
        )

    task_elements = _children(tasks_element, "Task")
    raw_tasks: list[dict] = []
    seen_uids: set[str] = set()
    used_codes: set[str] = set()

    for index, task_element in enumerate(task_elements, start=1):
        uid = _text(task_element, "UID")
        if uid == "0":
            # Microsoft Project can export a synthetic project-summary row. It
            # is context, not an operational Activity in Call-Off.
            continue
        if not uid:
            warnings.append(f"Task row {index} was skipped because it has no UID.")
            continue
        if uid in seen_uids:
            errors.append(f"Task UID {uid} appears more than once in the XML.")
            continue
        seen_uids.add(uid)

        name = _text(task_element, "Name")
        if not name:
            name = f"Unnamed task {uid}"
            warnings.append(f"Task UID {uid} has no name; a fallback label was used.")

        outline_level = max(_int_text(_text(task_element, "OutlineLevel"), 1), 1)
        source_code = (
            _text(task_element, "WBS")
            or _text(task_element, "OutlineNumber")
            or _text(task_element, "ID")
            or uid
        )
        activity_code = source_code[:100]
        if activity_code in used_codes:
            suffix = f"-{uid}"
            activity_code = f"{activity_code[: max(1, 100 - len(suffix))]}{suffix}"
            warnings.append(
                f"Activity code '{source_code}' was duplicated; UID {uid} was appended."
            )
        used_codes.add(activity_code)

        start_raw = _text(task_element, "Start")
        finish_raw = _text(task_element, "Finish")
        start = _normalise_datetime(start_raw)
        finish = _normalise_datetime(finish_raw)
        if start_raw and start is None:
            warnings.append(f"Task {activity_code} has an unreadable Start value.")
        if finish_raw and finish is None:
            warnings.append(f"Task {activity_code} has an unreadable Finish value.")

        duration_raw = _text(task_element, "Duration")
        duration = _duration_minutes(duration_raw)
        if duration_raw and duration is None:
            warnings.append(f"Task {activity_code} has an unreadable Duration value.")

        percent_complete = _int_text(_text(task_element, "PercentComplete"), 0)
        if percent_complete < 0 or percent_complete > 100:
            warnings.append(
                f"Task {activity_code} has PercentComplete outside 0-100; it was clamped."
            )
            percent_complete = max(0, min(100, percent_complete))

        raw_tasks.append(
            {
                "source_uid": uid,
                "activity_code": activity_code,
                "name": name[:250],
                "outline_level": outline_level,
                "planned_start": start,
                "planned_finish": finish,
                "duration_minutes": duration,
                "percent_complete": percent_complete,
                "is_milestone": _bool_text(_text(task_element, "Milestone")),
                "is_summary": _bool_text(_text(task_element, "Summary")),
                "element": task_element,
            }
        )

    if not raw_tasks:
        errors.append("No importable Programme tasks were found in the XML.")

    # Microsoft Project tasks are exported in outline order. Resolve hierarchy
    # from OutlineLevel instead of assuming a particular Area/Scope structure.
    hierarchy_stack: list[tuple[int, str]] = []
    tasks: list[ImportedTask] = []
    for raw in raw_tasks:
        level = raw["outline_level"]
        while hierarchy_stack and hierarchy_stack[-1][0] >= level:
            hierarchy_stack.pop()
        parent_uid = hierarchy_stack[-1][1] if hierarchy_stack else None
        tasks.append(
            ImportedTask(
                source_uid=raw["source_uid"],
                activity_code=raw["activity_code"],
                name=raw["name"],
                outline_level=level,
                parent_uid=parent_uid,
                planned_start=raw["planned_start"],
                planned_finish=raw["planned_finish"],
                duration_minutes=raw["duration_minutes"],
                percent_complete=raw["percent_complete"],
                is_milestone=raw["is_milestone"],
                is_summary=raw["is_summary"],
            )
        )
        hierarchy_stack.append((level, raw["source_uid"]))

    imported_uids = {task.source_uid for task in tasks}
    dependencies: list[ImportedDependency] = []
    dependency_keys: set[tuple[str, str, str]] = set()

    raw_by_uid = {item["source_uid"]: item for item in raw_tasks}
    for successor in tasks:
        task_element = raw_by_uid[successor.source_uid]["element"]
        for link in _children(task_element, "PredecessorLink"):
            predecessor_uid = _text(link, "PredecessorUID")
            if not predecessor_uid:
                warnings.append(
                    f"Task {successor.activity_code} contains a predecessor link with no UID."
                )
                continue
            if _bool_text(_text(link, "CrossProject")):
                warnings.append(
                    f"External predecessor {predecessor_uid} for {successor.activity_code} was not imported."
                )
                continue
            if predecessor_uid not in imported_uids:
                warnings.append(
                    f"Predecessor UID {predecessor_uid} for {successor.activity_code} was not found in the imported tasks."
                )
                continue

            dependency_type = _DEPENDENCY_TYPES.get(_text(link, "Type") or "1", "FS")
            lag_tenths = _int_text(_text(link, "LinkLag"), 0)
            lag_minutes = round(lag_tenths / 10)
            key = (predecessor_uid, successor.source_uid, dependency_type)
            if key in dependency_keys:
                continue
            dependency_keys.add(key)
            dependencies.append(
                ImportedDependency(
                    predecessor_uid=predecessor_uid,
                    successor_uid=successor.source_uid,
                    dependency_type=dependency_type,
                    lag_minutes=lag_minutes,
                )
            )

    return ProgrammeImportPreview(
        project_name=project_name,
        tasks=tuple(tasks),
        dependencies=tuple(dependencies),
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def create_import_preview(
    database: Session,
    project: Project,
    *,
    filename: str | None,
    content: bytes,
) -> tuple[ProgrammeImport, ProgrammeImportPreview]:
    programme = database.scalar(select(Programme).where(Programme.project_id == project.id))
    if programme is None:
        raise ProgrammeImportError("This project does not have a Programme container.")

    preview = parse_ms_project_xml(content)
    issues = [
        *({"severity": "warning", "message": message} for message in preview.warnings),
        *({"severity": "error", "message": message} for message in preview.errors),
    ]
    import_record = ProgrammeImport(
        programme_id=programme.id,
        source_type="ms_project_xml",
        source_filename=_safe_filename(filename),
        checksum=hashlib.sha256(content).hexdigest(),
        status="validated" if preview.can_confirm else "invalid",
        total_records=len(preview.tasks),
        imported_records=0,
        warning_count=len(preview.warnings),
        error_count=len(preview.errors),
        mapping_config={
            "format": "mspdi",
            "preview": preview.to_payload(),
        },
        validation_issues=issues or None,
        started_at=datetime.now(timezone.utc),
    )
    database.add(import_record)
    database.commit()
    database.refresh(import_record)
    return import_record, preview


def get_import_for_programme(
    database: Session,
    programme_id: uuid.UUID,
    import_id: uuid.UUID,
) -> ProgrammeImport | None:
    return database.scalar(
        select(ProgrammeImport).where(
            ProgrammeImport.id == import_id,
            ProgrammeImport.programme_id == programme_id,
        )
    )


def preview_from_import(import_record: ProgrammeImport) -> ProgrammeImportPreview:
    config = import_record.mapping_config or {}
    payload = config.get("preview")
    if not isinstance(payload, dict):
        raise InvalidProgrammeImportError("The validated import preview is unavailable.")
    return ProgrammeImportPreview.from_payload(payload)
