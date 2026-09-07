# Independent receiving-post geometry review

2026-09-06; inspected `/tmp/fence-planning-bom` dirty consumer changes. All dimensions below are synthetic, not Emblem manufacturer evidence.

## Mechanics verified

A direct local probe gave 1900 mm clear opening + 40/50 mm endpoint engagements = 1990 mm rail cut, with drawing x=-40 mm and width=1990 mm. Corner posts, stepped rails and inconsistent chosen post-face/clear-opening values were refused. Shared-post checks group actual physical post IDs and absolute world rail heights, require opposite collinear bays, and use the correct start/end engagement for reversed runs. Under this explicit outside-face datum and supported topology, host width minus both engagements is the remaining separation. An explicitly authored zero minimum permits exact touching; no clearance is silently invented.

The independent receiving/post-slot/kit test run passed 61 tests in 0.29 seconds before the final cross-band finding below. That result alone was not acceptance.

## Findings during independent review

1. Initially only exact rail centre heights were compared. Requested known face heights and same-side vertical-band overlap refusal; implemented by the consumer agent.
2. Level rails could be checked against a tilted post without projecting the host faces. Reproduced by setting all generated post tilt_deg to 10: two joint checks were accepted. The bounded subset now explicitly refuses non-plumb receiving posts, with a test.
3. The original unknown-post-width test removed an absent attrs key and did not affect authoritative Product.capabilities.face_width_mm. Independent run failed that refusal test (11 passed, one failed). Corrected test now removes the actual capability, which refuses as intended.
4. **Additional cross-side collision bypass found after the 61 passing tests:** for a 100 mm shared host, centres at 100 and 200 mm, left rail thickness/engagement pairs `(10,10)` and `(190,60)`, and right pairs `(190,60)` and `(10,10)`, each bay's vertical bands only touch. Each same-height pair leaves 30 mm separation and passes a required 30 mm minimum. But the two 190 mm thick diagonal rails overlap by 90 mm vertically and 20 mm axially (60+60−100). The checker accepted both same-height records without examining this physically colliding opposite-side pair. Reported to the implementing agent for all-opposite-overlapping-band validation or conservative refusal. Final fix/retest remains to be appended.

## Scope limits

This is executable private consumer geometry, not an agreed public Joint adapter or a measurement of real routed posts. Corners, angled entries, tilted posts, unsupported slopes, nonmatching partners and unresolved depth/engagement remain refusals. The model must separately establish manufacturer applicability, stock length, dimensional mapping and reviewed per-value provenance. Passing the synthetic tests cannot close those evidence/publication gaps.

## Final independent retest

The consumer now compares opposite-side vertical bands before same-height separation checks and conservatively refuses overlapping bands with unequal world centres. Re-running the exact asymmetric collision reproducer now raises `GenerationFailure: staggered receiving rail bands overlap across the post`.

The agent also added refusal for rail bands outside the panel height, preventing elevation clamping from moving the apparent rail centre, and for nonzero requirement overlap competing with the explicit endpoint engagements. Independent final run: **64 tests passed in 0.31 seconds** across `test_post_receiving_joint.py`, `test_post_slot.py` and `test_emblem_capabilities.py` (19 receiving-joint cases). The concrete findings above are fixed within the declared private subset; public mapping and real Emblem evidence remain outside this acceptance.
