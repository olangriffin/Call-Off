from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.backend.services.programme_workspace import build_programme_workspace


def activity(**overrides):
    values = {
        "activity_code": "A100",
        "name": "Coordinate design",
        "activity_type": "task",
        "planned_start": datetime(2026, 8, 10, tzinfo=timezone.utc),
        "planned_finish": datetime(2026, 8, 14, tzinfo=timezone.utc),
        "duration_minutes": None,
        "percent_complete": 40,
        "is_milestone": False,
        "is_summary": False,
        "status": "in_progress",
        "work_package": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ProgrammeWorkspaceTestCase(unittest.TestCase):
    def test_builds_timeline_geometry_and_summary_metrics(self) -> None:
        rows = [
            {"activity": activity(), "depth": 0},
            {
                "activity": activity(
                    activity_code="M100",
                    name="Design approved",
                    activity_type="milestone",
                    planned_start=None,
                    planned_finish=datetime(2026, 8, 21, tzinfo=timezone.utc),
                    percent_complete=100,
                    status="complete",
                ),
                "depth": 1,
            },
        ]

        workspace = build_programme_workspace(rows, today=date(2026, 8, 12))

        self.assertEqual(workspace.activity_count, 2)
        self.assertEqual(workspace.complete_count, 1)
        self.assertEqual(workspace.milestone_count, 1)
        self.assertIsNotNone(workspace.today_left_px)
        self.assertGreater(workspace.timeline_width_px, 0)
        self.assertTrue(workspace.timeline_ticks)
        self.assertFalse(workspace.rows[0].is_unscheduled)
        self.assertGreater(workspace.rows[0].bar_width_px or 0, 0)
        self.assertTrue(workspace.rows[1].is_milestone)
        self.assertFalse(workspace.rows[1].is_unscheduled)

    def test_keeps_undated_activity_visible_without_fake_bar(self) -> None:
        rows = [
            {
                "activity": activity(
                    planned_start=None,
                    planned_finish=None,
                    percent_complete=0,
                    status="not_started",
                ),
                "depth": 2,
            }
        ]

        workspace = build_programme_workspace(rows, today=date(2026, 8, 12))
        row = workspace.rows[0]

        self.assertTrue(row.is_unscheduled)
        self.assertIsNone(row.bar_left_px)
        self.assertIsNone(row.bar_width_px)
        self.assertEqual(row.start_label, "Not set")
        self.assertEqual(row.finish_label, "Not set")
        self.assertEqual(row.depth, 2)

    def test_activity_type_is_authoritative_for_milestone_display(self) -> None:
        rows = [
            {
                "activity": activity(
                    activity_type="milestone",
                    is_milestone=False,
                    planned_start=None,
                ),
                "depth": 0,
            }
        ]

        workspace = build_programme_workspace(rows, today=date(2026, 8, 12))

        self.assertTrue(workspace.rows[0].is_milestone)

        stale_flag_workspace = build_programme_workspace(
            [
                {
                    "activity": activity(
                        activity_type="task",
                        is_milestone=True,
                    ),
                    "depth": 0,
                }
            ],
            today=date(2026, 8, 12),
        )

        self.assertFalse(stale_flag_workspace.rows[0].is_milestone)

    def test_empty_programme_gets_a_useful_default_timeline(self) -> None:
        workspace = build_programme_workspace([], today=date(2026, 8, 12))

        self.assertEqual(workspace.activity_count, 0)
        self.assertEqual(workspace.date_range_label, "No dates scheduled")
        self.assertLess(workspace.timeline_start, date(2026, 8, 12))
        self.assertGreater(workspace.timeline_end, date(2026, 8, 12))


if __name__ == "__main__":
    unittest.main()
