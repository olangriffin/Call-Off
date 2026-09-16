from __future__ import annotations

import unittest

from app.backend.services.programme_import import parse_ms_project_xml


SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Project xmlns="http://schemas.microsoft.com/project">
  <Name>Trial Programme</Name>
  <Tasks>
    <Task>
      <UID>0</UID><ID>0</ID><Name>Trial Programme</Name><OutlineLevel>0</OutlineLevel><Summary>1</Summary>
    </Task>
    <Task>
      <UID>1</UID><ID>1</ID><WBS>1</WBS><Name>DH1</Name><OutlineLevel>1</OutlineLevel><Summary>1</Summary>
      <Start>2026-09-14T08:00:00</Start><Finish>2026-10-09T17:00:00</Finish><PercentComplete>0</PercentComplete>
    </Task>
    <Task>
      <UID>2</UID><ID>2</ID><WBS>1.1</WBS><Name>Walls</Name><OutlineLevel>2</OutlineLevel><Summary>1</Summary>
      <Start>2026-09-14T08:00:00</Start><Finish>2026-09-30T17:00:00</Finish><PercentComplete>0</PercentComplete>
    </Task>
    <Task>
      <UID>3</UID><ID>3</ID><WBS>1.1.1</WBS><Name>Design walls</Name><OutlineLevel>3</OutlineLevel>
      <Start>2026-09-14T08:00:00</Start><Finish>2026-09-18T17:00:00</Finish><Duration>PT40H0M0S</Duration><PercentComplete>100</PercentComplete>
    </Task>
    <Task>
      <UID>4</UID><ID>4</ID><WBS>1.1.2</WBS><Name>Install walls</Name><OutlineLevel>3</OutlineLevel>
      <Start>2026-09-21T08:00:00</Start><Finish>2026-09-25T17:00:00</Finish><Duration>PT40H0M0S</Duration><PercentComplete>25</PercentComplete>
      <PredecessorLink><PredecessorUID>3</PredecessorUID><Type>1</Type><LinkLag>600</LinkLag></PredecessorLink>
    </Task>
    <Task>
      <UID>5</UID><ID>5</ID><WBS>1.2</WBS><Name>Handover</Name><OutlineLevel>2</OutlineLevel>
      <Start>2026-10-09T17:00:00</Start><Finish>2026-10-09T17:00:00</Finish><Duration>PT0H0M0S</Duration><PercentComplete>0</PercentComplete><Milestone>1</Milestone>
    </Task>
  </Tasks>
</Project>
"""


class ProgrammeImportParserTestCase(unittest.TestCase):
    def test_parses_project_xml_into_hierarchy_and_dependencies(self) -> None:
        preview = parse_ms_project_xml(SAMPLE_XML)

        self.assertEqual(preview.project_name, "Trial Programme")
        self.assertEqual(len(preview.tasks), 5)
        self.assertEqual(preview.milestone_count, 1)
        self.assertEqual(len(preview.dependencies), 1)
        self.assertTrue(preview.can_confirm)
        self.assertEqual(preview.errors, ())

        by_uid = {task.source_uid: task for task in preview.tasks}
        self.assertIsNone(by_uid["1"].parent_uid)
        self.assertEqual(by_uid["2"].parent_uid, "1")
        self.assertEqual(by_uid["3"].parent_uid, "2")
        self.assertEqual(by_uid["4"].parent_uid, "2")
        self.assertEqual(by_uid["5"].parent_uid, "1")
        self.assertEqual(by_uid["3"].activity_code, "1.1.1")
        self.assertEqual(by_uid["3"].duration_minutes, 2400)
        self.assertTrue(by_uid["5"].is_milestone)

        dependency = preview.dependencies[0]
        self.assertEqual(dependency.predecessor_uid, "3")
        self.assertEqual(dependency.successor_uid, "4")
        self.assertEqual(dependency.dependency_type, "FS")
        self.assertEqual(dependency.lag_minutes, 60)

    def test_invalid_xml_blocks_confirmation(self) -> None:
        preview = parse_ms_project_xml(b"<not-project><Tasks /></not-project>")

        self.assertFalse(preview.can_confirm)
        self.assertTrue(preview.errors)

    def test_duplicate_wbs_codes_are_made_unique_without_losing_tasks(self) -> None:
        xml = b"""<Project><Tasks>
          <Task><UID>1</UID><WBS>1</WBS><Name>One</Name><OutlineLevel>1</OutlineLevel></Task>
          <Task><UID>2</UID><WBS>1</WBS><Name>Two</Name><OutlineLevel>1</OutlineLevel></Task>
        </Tasks></Project>"""

        preview = parse_ms_project_xml(xml)

        self.assertEqual(len(preview.tasks), 2)
        self.assertNotEqual(preview.tasks[0].activity_code, preview.tasks[1].activity_code)
        self.assertTrue(preview.warnings)


if __name__ == "__main__":
    unittest.main()
