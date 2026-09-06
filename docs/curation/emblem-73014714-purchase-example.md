# Emblem — purchase-count checkpoint

The user chose **A: purchase complete kits** and accepted this single-panel
major-product example. This counts one authored standalone full-panel bay;
it does not derive bay count from a measured run length.

```text
End post — panel kit — End post
```

| Purchase item | Manufacturer model | Count |
|---|---|---:|
| Emblem 6x8 White complete panel kit | 73014714 | 1 |
| White end post, 5 x 5 x 108 inches | 73045785 | 2 |
| White contemporary post top | 73013956 | 2 |

These are manufacturer catalog item counts, not verified retailer carton or
multipack quantities. The kit covers its panel contents;
the example adds no separate board or rail purchase lines. Source: the
[exact project sheet](../../workspace/derived/doc-1e71ed3bf8a5/pages/0001.png).
The graph and source references are retained in the
[machine-readable example](../../workspace/reports/emblem-73014714-purchase-example.json).
Checks confirm two unique stations, correct open-path degrees, source resolution,
and the expected item counts. These are example calculations, not Planning output.

Concrete, gravel, adhesive consumption and conditional reinforcement remain
unquantified. This is a kit/post/cap purchase-count checkpoint, not a complete
installation order. There are no gates, corners, cuts or pricing in this scenario.

## What the contract check establishes

- `FenceModel.post` supplies posts per station, with its nested cap. Shared posts
  belong outside `PanelSpec` (§3.4).
- `InfillSpec.supply = assembly` is an infill field (§3.3). Changing it alone
  does not represent a whole panel kit including frame rails.
- §3.4 describes kit crediting to avoid buying contained components twice, but
  explicitly identifies a consumer implementation gap. Whole-kit Product matching
  and coverage need verification against Planning before this becomes executable
  contract output. The example introduces no public schema or shared kit type.

## Requirements for this objective

| Category | Treatment |
|---|---|
| Kit identity, post products, chosen cap | Supported by existing project sheet |
| Number of full-panel bays, stations and station roles | Authored in this example; real projects need their layout |
| Whole-kit purchase coverage and matching | Consumer representation must be verified |
| Run length, cut panels, gates, conditional installation materials | Needed when those enter the real project |
| Board thickness, channel depth and component cut lengths | Remain incomplete for fabrication; do not block counting already-specified full-panel kits |

The previous field-presence audit is still useful for the unfinished geometric
model. Its missing-field total is not the acceptance criterion for this purchase
example. User acceptance covers the visible three-line major-product count, not
new dimensions, installation quantities or pack-size conversions. The previous
three-panel artifact is retained separately as
`workspace/reports/emblem-73014714-three-panel-count-example.json`.

## Independent assembly review

Two agents independently reviewed assembly and purchasing logic. The root agent
checked their findings against the sources. Both agree that 1 kit, 2 end posts
and 2 caps is the correct basic catalog-item list for this example.

Corrections made:

- Replaced the stale three-panel active example with the accepted single-panel case.
- Added two U-channels to private kit inventory, with first-board tongue and
  last-board groove edge assignments (installation manual pp2,4). They are not
  separate purchases. Their contract Part type and slot mapping remain incomplete;
  an inventory record is not a completed geometric graph.
- Added concrete, gravel/filler and cap adhesive as explicit required installation
  materials, with quantities unresolved. The sheet names adhesive 73047688;
  it does not establish how many tubes this installation consumes.
- Recorded engaging the panel with the second post before fixing that post in
  concrete (manual pp3,7).

The walkthrough follows first-post setting → bottom rail → handed end channels →
boards → top rail → second-post engagement → second-post fixing → glued caps.
It is a review trace with source anchors, not a generated contract Procedure or
a substitute for the manufacturer's instructions.

Wind configurations remain conditional; the ordinary 7-inch-rail insert exception
does not eliminate wind-related post reinforcement. The guide's gravel-depth
passages need resolution for the selected installation before calculating bags.
Neither uncertainty changes the accepted major-product count.

One reviewer initially claimed a citation named the panel dimension cell. Live
reference resolution showed it names the full project-sheet page, including the
post rows; that finding was withdrawn. It is not a provenance defect.

Validation:

```sh
python3 scripts/audit_purchase_example.py workspace/reports/emblem-73014714-purchase-example.json --report workspace/reports/emblem-73014714-purchase-audit.json
python3 -m unittest discover -s tests -p 'test_purchase_example.py'
```

Purchase-example checks pass; **installation_ready remains false**. Nine new
tests cover counts, shared posts, duplicate bays, wrong post roles, duplicated
loose-rail purchases, channel presence/handedness, second-post sequencing and false
completeness claims. The 14 existing model-audit tests also pass. All 26 citation
occurrences in the purchase example resolve. The geometric model audit still
exits 2 for incomplete fields; no snapshot was published.
