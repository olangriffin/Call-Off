from __future__ import annotations

import uuid
import unittest
from datetime import date
from types import SimpleNamespace

from app.backend.services.package_identification import (
    build_package_identification_preview,
    find_package_identification_candidate,
)


def _activity(
    number: int,
    code: str,
    name: str,
    *,
    parent: SimpleNamespace | None = None,
    start: date | None = None,
    finish: date | None = None,
    package_code: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID(int=number),
        activity_code=code,
        name=name,
        parent_activity_id=parent.id if parent else None,
        planned_start=start,
        planned_finish=finish,
        work_package=(
            SimpleNamespace(code=package_code) if package_code is not None else None
        ),
    )


class PackageIdentificationPreviewTestCase(unittest.TestCase):
    def test_groups_leaf_activity_evidence_by_second_hierarchy_level(self) -> None:
        area = _activity(1, "A100", "DH1")
        walls = _activity(2, "A110", "Walls", parent=area)
        design = _activity(3, "A111", "Design", parent=walls)
        procurement = _activity(4, "A112", "Procurement", parent=walls)
        installation = _activity(5, "A113", "Installation", parent=walls)
        drawing = _activity(
            6,
            "A111-1",
            "Issue wall drawings",
            parent=design,
            start=date(2026, 10, 1),
            finish=date(2026, 10, 5),
        )
        order = _activity(
            7,
            "A112-1",
            "Order wall materials",
            parent=procurement,
            start=date(2026, 10, 6),
            finish=date(2026, 10, 10),
        )
        install = _activity(
            8,
            "A113-1",
            "Install walls",
            parent=installation,
            start=date(2026, 10, 15),
            finish=date(2026, 10, 20),
        )

        preview = build_package_identification_preview(
            [
                area,
                walls,
                design,
                procurement,
                installation,
                drawing,
                order,
                install,
            ]
        )

        self.assertEqual(len(preview.candidates), 1)
        candidate = preview.candidates[0]
        self.assertEqual(candidate.anchor_activity_id, walls.id)
        self.assertEqual(candidate.proposed_code, "PKG-A110")
        self.assertEqual(candidate.proposed_name, "DH1 — Walls")
        self.assertEqual(candidate.what_label, "Walls")
        self.assertEqual(candidate.where_label, "DH1")
        self.assertEqual(candidate.start_date, date(2026, 10, 1))
        self.assertEqual(candidate.finish_date, date(2026, 10, 20))
        self.assertEqual(candidate.activity_count, 3)
        self.assertEqual(candidate.evidence_strength, "Structured hierarchy")
        self.assertFalse(candidate.already_confirmed)
        self.assertEqual(preview.source_activity_count, 8)
        self.assertEqual(preview.candidate_activity_count, 3)

    def test_same_scope_name_under_different_contexts_stays_separate(self) -> None:
        area_one = _activity(10, "A100", "DH1")
        walls_one = _activity(11, "A110", "Walls", parent=area_one)
        install_one = _activity(12, "A111", "Install walls", parent=walls_one)

        area_two = _activity(20, "B100", "DH2")
        walls_two = _activity(21, "B110", "Walls", parent=area_two)
        install_two = _activity(22, "B111", "Install walls", parent=walls_two)

        preview = build_package_identification_preview(
            [area_one, walls_one, install_one, area_two, walls_two, install_two]
        )

        self.assertEqual(
            [candidate.proposed_name for candidate in preview.candidates],
            ["DH1 — Walls", "DH2 — Walls"],
        )
        self.assertEqual(
            [candidate.proposed_code for candidate in preview.candidates],
            ["PKG-A110", "PKG-B110"],
        )

    def test_existing_deterministic_package_code_marks_candidate_confirmed(self) -> None:
        area = _activity(23, "A200", "DH3")
        ceilings = _activity(24, "A210", "Ceilings", parent=area)
        install = _activity(25, "A211", "Install ceilings", parent=ceilings)

        preview = build_package_identification_preview(
            [area, ceilings, install],
            existing_package_codes={"PKG-A210"},
        )

        self.assertTrue(preview.candidates[0].already_confirmed)

    def test_legacy_activity_links_are_evidence_not_candidate_identity(self) -> None:
        area = _activity(30, "A100", "Area A")
        ceilings = _activity(31, "A110", "Ceilings", parent=area)
        design = _activity(
            32,
            "A111",
            "Design ceilings",
            parent=ceilings,
            package_code="PKG-01",
        )
        install = _activity(33, "A112", "Install ceilings", parent=ceilings)

        preview = build_package_identification_preview(
            [area, ceilings, design, install]
        )
        candidate = preview.candidates[0]

        self.assertEqual(candidate.linked_package_codes, ("PKG-01",))
        self.assertTrue(candidate.partially_linked)
        self.assertFalse(candidate.fully_linked)
        self.assertEqual(preview.linked_activity_count, 1)
        self.assertIs(
            find_package_identification_candidate(preview, ceilings.id),
            candidate,
        )

    def test_flat_programme_falls_back_to_single_activity_candidate(self) -> None:
        milestone = _activity(
            40,
            "M100",
            "Plant room handover",
            finish=date(2026, 11, 12),
        )

        preview = build_package_identification_preview([milestone])
        candidate = preview.candidates[0]

        self.assertEqual(candidate.proposed_code, "PKG-M100")
        self.assertEqual(candidate.proposed_name, "Plant room handover")
        self.assertIsNone(candidate.where_label)
        self.assertEqual(candidate.start_date, date(2026, 11, 12))
        self.assertEqual(candidate.finish_date, date(2026, 11, 12))
        self.assertEqual(candidate.evidence_strength, "Single activity")


if __name__ == "__main__":
    unittest.main()
