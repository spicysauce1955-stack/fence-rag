"""Review vectors for an unratified proposal, isolated from publication."""
from copy import deepcopy
import unittest

import context  # repository import path
from fence_evidence.canonical import canonical_bytes
from scripts.geometry_provenance_proposal import build_packet, decode_unique, examples, validate_owner


class TestGeometryProvenanceProposal(unittest.TestCase):
    def setUp(self):
        self.fixture, self.joint, self.placement = examples()

    def validate(self, owner, kind='Joint'):
        return validate_owner(kind, owner, self.fixture['source_refs'], self.fixture['source_docs'])

    def test_positive_and_refusal_vectors_execute_without_claiming_admission(self):
        packet = build_packet()
        self.assertFalse(packet['publishable'])
        self.assertFalse(packet['consumer_adapter_implemented'])
        self.assertEqual(len(packet['vectors']), 11)
        self.assertEqual(sum(v['result'] == 'refused' for v in packet['vectors']), 8)

    def test_optional_null_stays_null_and_has_no_numeric_association(self):
        before = canonical_bytes(self.joint)
        result = self.validate(self.joint)
        self.assertIsNone(result['owner']['shared_host_gap'])
        self.assertEqual(result['null_obligations'][0]['target'], '/shared_host_gap')
        self.assertEqual(canonical_bytes(self.joint), before)
        self.joint['field_provenance']['/shared_host_gap'] = deepcopy(self.joint['field_provenance']['/channel_depth'])
        with self.assertRaises(ValueError):
            self.validate(self.joint)

    def test_zero_is_explicit_and_requires_classification(self):
        self.joint['shared_host_gap'] = {'amount_milli': 0, 'unit': 'mm', 'value_raw': ['0 mm (synthetic)']}
        with self.assertRaises(ValueError):
            self.validate(self.joint)
        self.joint['field_provenance']['/shared_host_gap'] = deepcopy(self.joint['field_provenance']['/channel_depth'])
        self.assertEqual(self.validate(self.joint)['null_obligations'], [])

    def test_missing_optional_field_does_not_invoke_default(self):
        del self.joint['insertion_margin']
        with self.assertRaises(ValueError):
            self.validate(self.joint)

    def test_duplicate_pointer_is_rejected_before_json_collapse(self):
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            decode_unique('{"field_provenance":{"/offset":{},"/offset":{}}}')

    def test_undeclared_owner_and_field_refuse(self):
        with self.assertRaises(ValueError):
            self.validate(self.joint, 'Distributed')
        self.joint['extra_allowance'] = {'amount_milli': 10, 'unit': 'mm', 'value_raw': ['synthetic']}
        with self.assertRaises(ValueError):
            self.validate(self.joint)

    def test_field_classifications_are_independent_and_preserved(self):
        provenance = self.joint['field_provenance']['/insertion_margin']
        # Validate a registry-supported alternate classification, not a fabricated review.
        from fence_evidence.snapshot import SOURCE_CLASSES
        provenance['source_class'] = next(c for c in sorted(SOURCE_CLASSES) if c != 'ai_proposal')
        before = canonical_bytes(self.joint)
        self.assertEqual(canonical_bytes(self.validate(self.joint)['owner']), before)

    def test_bool_and_float_milli_values_are_not_integer_quantities(self):
        for value in (True, 88900.0, -1):
            with self.subTest(value=value):
                self.placement['offset']['amount_milli'] = value
                with self.assertRaises(ValueError):
                    self.validate(self.placement, 'FromBottom')

    def test_precision_vectors_expose_round_before_repeat_loss(self):
        p = build_packet()['precision']
        self.assertEqual(p['placement_milli_mm'], 88900)
        self.assertEqual(p['exact_repeated_milli_mm'], 2286000)
        self.assertEqual(p['loss_milli_mm'], 6000)

    def test_unknown_source_document_and_duplicate_citation_refuse(self):
        self.fixture['source_docs'] = []
        with self.assertRaises(ValueError):
            self.validate(self.joint)
        self.fixture, self.joint, _ = examples()
        cites = self.joint['field_provenance']['/channel_depth']['cites']
        cites.append(deepcopy(cites[0]))
        with self.assertRaises(ValueError):
            self.validate(self.joint)


if __name__ == '__main__':
    unittest.main()
