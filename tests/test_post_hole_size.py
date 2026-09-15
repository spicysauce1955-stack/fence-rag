"""A hole size stated per post designation is a footing diameter, conditioned.

`[measured]` 2026-09-15: six installation guides print

    - Hole size for 4x4 posts = approximately 10"
    - Hole size for 5x5 posts = approximately 12"

**100 times**, and the extractor reads none of them. `footing_diameter_in`
requires the word *diameter* adjacent to the number (a narrowing made
deliberately, so the match cannot bridge to an unrelated number), and this
vernacular never uses it. Two independent machine readings of the same guides
found every occurrence, which is how the gap surfaced.

`footing_diameter_mm` is one of the four parameters that already publish, so
this is a measurement with a live route to the boundary — but it cannot take it
naively. **The two sizes are different values of the same parameter, separated
only by the post they apply to, and both are printed inside ONE element:**

    '• Dig holes 30" deep or to frost line
     - Hole size for 4x4 posts = approximately 10"
     - Hole size for 5x5 posts = approximately 12"
     • Clean holes and check for straight walls'

So an element-scoped condition (what `_conditions` supplies) would attach both
post sizes to both diameters, and to the 30" depth beside them, which is not
post-dependent at all. The condition has to be bound by the match that carried
it, and it is `stated` rather than `assumed` because the document puts the post
designation and the number in the same clause.
"""
import unittest

from context import ROOT  # noqa: F401
from fence_evidence.facts import _scan_text
from fence_evidence.parameters import CONDITION_SCOPE

ELEMENT = ('• Dig holes 30" deep or to frost line\n'
           '- Hole size for 4x4 posts = approximately 10"\n'
           '- Hole size for 5x5 posts = approximately 12"\n'
           '• Clean holes and check for straight walls')


def _diameters(text):
    return [m for m in _scan_text(text) if m["fact_type"] == "footing_diameter_in"]


class TestAHoleSizePerPostIsAFootingDiameter(unittest.TestCase):
    def test_the_stated_hole_size_is_read_as_a_diameter(self):
        """The measured gap: 100 occurrences, none of them extracted.

        Fails today because every `footing_diameter_in` pattern requires the
        word *diameter*, which this phrasing never uses.
        """
        got = _diameters('- Hole size for 4 x 4 posts = approximately 10"')
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["value_normalized"], 10.0)

    def test_both_sizes_in_one_element_stay_separate(self):
        """The trap. One element, two diameters, and a depth that is neither.

        If the two ever collapse into one fact, or borrow each other's post
        size, the store holds a footing width that is wrong for half the posts
        it claims to cover.
        """
        got = _diameters(ELEMENT)
        self.assertEqual(sorted(m["value_normalized"] for m in got), [10.0, 12.0])

    def test_each_diameter_carries_the_post_it_applies_to(self):
        """A 10-inch hole is only right for a 4x4. Published bare, it is wrong.

        `footing_diameter_mm` publishes today, so an unconditioned value here
        crosses the boundary as though it held for every post.
        """
        by_value = {m["value_normalized"]: m for m in _diameters(ELEMENT)}
        self.assertEqual(by_value[10.0]["conditions"], {"post_size": "4x4"})
        self.assertEqual(by_value[12.0]["conditions"], {"post_size": "5x5"})

    def test_the_condition_is_stated_not_assumed(self):
        """Proximity is `assumed`; the same clause is `stated`.

        Everything `_conditions` captures is `assumed`, because a regex near a
        number does not establish that the document bound them (G15). Here the
        document does: the post designation and the size are one sentence.
        """
        got = _diameters('- Hole size for 5x5 posts = approximately 12"')
        self.assertEqual(got[0]["condition_basis"], "stated")

    def test_the_depth_beside_them_takes_no_post_size(self):
        """The reason the condition cannot be element-scoped.

        `Dig holes 30" deep` is in the same element and applies to every post.
        Giving it a `post_size` would invent a restriction the source does not
        state.
        """
        depth = [m for m in _scan_text(ELEMENT)
                 if m["fact_type"] == "footing_depth_in"]
        self.assertTrue(depth, "sanity: the 30-inch depth is still extracted")
        for m in depth:
            self.assertNotIn("post_size", m.get("conditions") or {})

    def test_post_size_is_a_publishable_condition_dimension(self):
        """Without this the fix reaches the store and stops.

        `parameters.CONDITION_SCOPE` is the closed set a published condition key
        must be in; a key absent from it is refused at publish time. A registry
        addition is not an amendment and needs no negotiation.
        """
        self.assertIn("post_size", CONDITION_SCOPE)


class TestItDoesNotOverreach(unittest.TestCase):
    def test_a_diameter_with_no_post_named_stays_unconditioned(self):
        """The existing behaviour this must not disturb."""
        got = _diameters("footing 8 in. diameter")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].get("conditions") or {}, {})

    def test_a_hole_size_naming_no_post_is_not_given_one(self):
        """`Hole size = 10"` states no post. Inventing one is worse than a miss."""
        got = _diameters('- Hole size = approximately 10"')
        for m in got:
            self.assertEqual(m.get("conditions") or {}, {})


if __name__ == "__main__":
    unittest.main()
