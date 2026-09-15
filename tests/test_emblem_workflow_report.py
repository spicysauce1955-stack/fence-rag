"""Progress reports describe the current published slice after review decisions."""
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.emblem_claims import BOARD_ID, PART_READINGS, READINGS
from scripts.advance_emblem import markdown, publication_slice


class TestEmblemWorkflowReport(unittest.TestCase):
    def render(self, parts, facts):
        result = publication_slice(parts, facts)
        result.update(snapshot_id='test-snapshot', full_model_admitted=False,
                      assembly_validated=False, required_geometry=[],
                      publication_exclusions=[], assembly_remaining=[])
        return result, markdown(result)

    def facts(self, rejected=()):
        return [{'fact_type': reading[1],
                 'review_status': 'rejected' if reading[1] in rejected else 'extracted'}
                for reading in READINGS]

    def test_colour_rejection_reports_only_cap_published_and_three_withheld(self):
        cap_id = PART_READINGS[-1][0]
        result, rendered = self.render([{'id': cap_id}], self.facts(('component_colour',)))
        self.assertEqual(result['published_exact_part_count'], 1)
        self.assertEqual(result['withheld_exact_part_count'], 3)
        self.assertIn('Published exact Parts: **1**. Withheld exact Parts: **3**.', rendered)
        self.assertIn(f'| `{cap_id}` | published |', rendered)
        self.assertIn(f'| `{BOARD_ID}` | withheld | Rejected readings: component_colour |', rendered)
        self.assertNotIn(f'| `{BOARD_ID}` | published |', rendered)
        self.assertNotIn('Completed supported slice', rendered)

    def test_no_readings_reports_every_expected_part_withheld(self):
        result, rendered = self.render([], [])
        self.assertEqual(result['published_exact_part_count'], 0)
        self.assertEqual(result['withheld_exact_part_count'], 4)
        self.assertIn('Missing readings: nominal_board_width_in, component_colour', rendered)
        self.assertNotIn('| published |', rendered)

    def test_complete_slice_excludes_unrelated_parts_from_counts(self):
        parts = [{'id': reading[0]} for reading in PART_READINGS]
        result, rendered = self.render(parts + [{'id': 'unrelated-part'}], self.facts())
        self.assertEqual(result['published_exact_part_count'], 4)
        self.assertEqual(result['withheld_exact_part_count'], 0)
        self.assertEqual(result['withheld_exact_parts'], [])
        self.assertNotIn('unrelated-part', rendered)
        self.assertIn('Assembly validated: **False**.', rendered)
