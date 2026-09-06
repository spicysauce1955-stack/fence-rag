# Emblem — seven-panel layout review

An authored example: five full panels form an L, and a separate straight run has
two full panels. No gates, cuts, slopes or measured site dimensions are asserted.
Each link below is one full panel kit.

```text
A0 End — A1 Line — A2 Line — A3 Corner
                               |
                            A4 Line
                               |
                            A5 End

B0 End — B1 Line — B2 End       (separate run)
```

| Catalog item | Model | Count |
|---|---|---:|
| Emblem White panel kit | 73014714 | 7 |
| End post | 73045785 | 4 |
| Line post | 73045783 | 4 |
| Corner post | 73045784 | 1 |
| Contemporary post cap | 73013956 | 9 |

The L contains 5 panels and 6 unique posts; the separate run contains 2 panels
and 3 posts. Thus **7 panels + 2 open runs = 9 posts**. The single-run shortcut
of adding just one post to the total would be wrong. Fourteen end U-channels
are contained within the seven kits, not separate purchases. Board count inside
each kit remains unverified. Counts are catalog items, not retailer cartons.

## What was exercised

- Connected-component counting: the separate run needs two endpoints and its own
  initial-post operation.
- Corner classification: opposite schematic directions require a line post;
  perpendicular directions require a corner post. Degree two alone is insufficient.
- Shared-post assembly: A3 receives the third panel, then starts the fourth; it
  is bought, fixed and capped once. Orient its routed faces before fixing it.
- Per-bay sequencing: receiving-post engagement precedes that post's fixing.
  Each bay gets its own channel, board and rail assembly steps.

The checked logical trace has 53 events: 2 initial-post settings, 6 actions for
each of 7 bays, and 9 caps. Tests independently check one fixing per station and
that every starting post is already set before its bay's bottom rail operation.
Site preparation and footing quantities are outside this trace.

The checker also rejects duplicate stations/bays/run identities, incorrect post
roles, unsupported branching, cycles, diagonal or zero-length bays, coincident
stations, unmodeled intersections, and assembly traversals that omit or repeat
stations or bays. Its coordinates are dimensionless schematic locations; they
must not be used as installation dimensions.

## Evidence and limits

Catalog rows and roles come from the [exact project sheet](../../workspace/derived/doc-1e71ed3bf8a5/pages/0001.png).
The [local installation manual](../../manuals/freedom-outdoor-living/FREEDOM-WEB-PrivacyKit_Ready-to-Assemble-Privacy-Vinyl-Fence-Install.pdf)
pp3–4,7 supports the sequential full-privacy assembly. The exact-model linkage
to its revised edition is retained in the model draft. Thirty citation occurrences
in this example resolve to their recorded document versions.

An independent agent confirmed all counts and the corner/separate-run logic.
The review exposed limits in the old one-straight-run checker; the checker now
supports explicitly declared orthogonal open runs and records bay/post references
in its expanded trace.

**This does not verify physical corner fit.** Rail-end clearance inside the corner
post remains unmeasured. Concrete, gravel and adhesive quantities, wind-related
reinforcement, supplier pack conversion, and whole-kit consumption by Planning
remain unresolved. `installation_ready` stays false. No complete contract model,
generated Planning plan or supplier order was created.

## Reproduce

```sh
python3 scripts/audit_purchase_example.py workspace/reports/emblem-73014714-complex-purchase-example.json --report workspace/reports/emblem-73014714-complex-purchase-audit.json
python3 -m unittest discover -s tests -p 'test_purchase_example.py'
```

Results: complex example passes; the original single-panel case still passes;
19 tests pass, including negative controls. See the
[example JSON](../../workspace/reports/emblem-73014714-complex-purchase-example.json)
and [audit with expanded assembly trace](../../workspace/reports/emblem-73014714-complex-purchase-audit.json).
