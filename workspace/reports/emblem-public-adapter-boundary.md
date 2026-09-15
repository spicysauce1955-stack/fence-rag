# Public model adapter boundary — independently checked

Date: 2026-09-06. Consumer checkout: `/tmp/fence-planning-bom`, base revision `9de94eb06d8e997d9be098dedd5b6a6b2eb4024d`, including the current uncommitted capability changes. This is a software/semantic boundary gap, separate from missing Emblem manufacturer dimensions. No positive public-adapter acceptance is claimed.

## Measured mismatch

| Public definition | Actual private consumer | Consequence |
| --- | --- | --- |
| `PostSlot.joint: Joint`, `contains` — `docs/integration/knowledge-datamodel.md:829` | `src/fenceai/fencemodel/model.py:480` exposes only `key`, `requirement`, `cap` | Post receiving geometry has no executable destination. Nonempty post contents also have no same-host destination. |
| `Joint.channel_depth`, `insertion_margin`, `shared_host_gap`, `gap_reason` — datamodel line 561 | FrameSlot has `joint` kind plus `channel_depth_mm` and `insertion_margin_mm` — consumer model line 369 | Only the frame receiving-depth subset has a direct mapping. Shared-host gap and its reason have no matching calculation. |
| `Member.joint: Joint` — datamodel line 571 | Member has a joint-kind string and separate base/top engagement — consumer model line 423 | A Member's own receiving channel cannot be replaced by its engagement into a different receiving frame. |
| A shared post is one object across bays — datamodel lines 839–854 | FrameSlot `post_joint: unstated|lands|through` — consumer model lines 97, 378–382 | This enum describes continuity capability, not a post cavity, insertion margin or separation between adjacent rail ends. |
| `insertion_margin: null` publishes a Gap, never zero — datamodel lines 640–644 | Private frame insertion margin defaults to zero — consumer model line 405 | An adapter must explicitly refuse or propagate a missing-value gap. It cannot apply the private default as a manufacturer assertion. |

Observed with the actual consumer virtual environment:

```python
from fenceai.fencemodel.model import PostSlot
payload = {
    "key": "post", "requirement": {"part_id": "test/post", "qty": 1},
    "cap": None,
    "joint": {
        "kind": "channel",
        "channel_depth": {"amount_milli": 25000, "unit": "mm", "value_raw": ["25 mm"]},
        "insertion_margin": {"amount_milli": 1000, "unit": "mm", "value_raw": ["1 mm"]},
    },
}
parsed = PostSlot.model_validate(payload)
assert list(PostSlot.model_fields) == ["key", "requirement", "cap"]
assert "joint" not in parsed.model_dump()
```

Result: parsing succeeds and discards the entire Joint. These numbers are synthetic adversarial inputs, not Emblem dimensions. Saving the original in a sidecar preserves provenance but does not make the absent consumer behavior execute.

## Why the rail Joint is not the post Joint

The public definition explicitly says channel depth describes how deeply **this slot receives another**. For a horizontal rail receiving a vertical board, the consumer frame fields and member base/top engagement operate together. `src/fenceai/fencemodel/resolve.py:174–200` documents and stores that relationship. The rail's receiving channel concerns the board-to-rail joint.

A post receiving the ends of rails is a different host and joint. The datamodel discussion at lines 646–658 explicitly places separation between rail ends inside the shared post on the Joint: the two rails belong to different bays. Mapping this to each rail's board-receiving channel would change the wrong geometry and duplicate a shared-post condition. `post_joint=lands|through` supplies no depth or clearance and cannot substitute for it.

## Required work before lossless publication and consumption

1. Define and implement post-host receiving geometry, including which rail ends engage which host, the coordinate datum and engagement calculation. The existing public PostSlot and Joint describe a host, but no executable post-joint resolver exists in the inspected consumer.
2. Define how two adjacent bays jointly satisfy `shared_host_gap`, including line versus corner topology and responsibility for evaluating the single shared post. Do not copy the same allowance onto both rails without an explicit rule.
3. Implement or explicitly refuse Member receiving Joint fields and contained-host branches. Preserve all source meanings; a sidecar alone does not consume them.
4. Build a wire adapter with a declared supported subset and exact integer-milli conversion. Fractional millimetres require an approved rounding policy; they must not silently truncate. Bind the complete original model, referenced Parts and evidence to the review digest.
5. Validate through the real PartLibrary and model validator, then exercise generated single-panel and multi-bay BOMs. Verify physical counts, package credits, host geometry and shared-post quantities independently.

The current producer preflight requires a complete explicit post; weakening that to `post: null` solely to produce a positive adapter test would remove a required part of this product's model. No such workaround or refusal-only duplicate adapter was created.
