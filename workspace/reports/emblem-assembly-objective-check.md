# Emblem publication and assembly checklist

Target: exact white 6×8 model 73014714, including assembly and component BOM.

Verified snapshot: `b5048772101e18513a9cbd2c913978da05046fced986e03c42afddc5c5b19ec7`.
Full model admitted: **False**. Assembly validated: **False**.

## Current Part publication

Published exact Parts: **4**. Withheld exact Parts: **0**.

| Part | State | Detail |
|---|---|---|
| `mfr/freedom-outdoor-living/73013956` | published | Current review projection |
| `mfr/freedom-outdoor-living/emblem-73014714-board` | published | Current review projection |
| `mfr/freedom-outdoor-living/emblem-73014714-rail-a` | published | Current review projection |
| `mfr/freedom-outdoor-living/emblem-73014714-rail-b` | published | Current review projection |

Board width remains nominal, separate from installed pitch. Cap dimensions remain nominal, separate from mating clearances.
Readings remain unreviewed unless an existing human review says otherwise.

## Geometry needed for verified fit calculations

| Field | Meaning | State |
|---|---|---|
| `/default_spec/frame/0/joint/channel_depth` | Bottom rail board-pocket depth | missing |
| `/default_spec/frame/1/joint/channel_depth` | Top rail board-pocket depth | missing |
| `/default_spec/infill/pattern/0/base_engagement` | Board seating in bottom rail | missing |
| `/default_spec/infill/pattern/0/top_engagement` | Board seating in top rail | missing |
| `/default_spec/infill/pattern/0/joint/channel_depth` | Board groove receiving depth | missing |
| `/post/joint/channel_depth` | Post receiving depth for a rail end | missing |

## Complete executable model exclusions

| Field | Reason |
|---|---|
| `/grade` | missing_value: Required model field is absent. |
| `/height_support` | missing_value: Required model field is absent. |
| `/option_axes` | missing_value: Required model field is absent. |
| `/variants` | missing_value: Required model field is absent. |
| `/layout_policy` | missing_value: Required model field is absent. |
| `/assembly` | missing_value: Required model field is absent. |
| `/option_axes` | invalid_shape: Explicit list required. |
| `/variants` | invalid_shape: Explicit list required. |
| `/layout_policy` | invalid_shape: Explicit list required. |
| `/assembly` | invalid_shape: Explicit list required. |
| `/height_support` | missing_value: Explicit height support required. |
| `/grade` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/grade` | invalid_grade: Explicit supported grade required. |
| `/height_support` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/height_support` | unsupported_height_support: This profile requires explicit discrete supported heights. |
| `/default_spec/frame/0/joint/shared_host_gap` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/0/joint/gap_reason` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/0/joint/kind` | uncited: Nonempty source citations are required. |
| `/default_spec/frame/0/joint/channel_depth` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/0/joint/channel_depth` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/frame/0/joint/insertion_margin` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/0/joint/insertion_margin` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/frame/0/orientation` | uncited: Nonempty source citations are required. |
| `/default_spec/frame/0/placement` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/0/placement` | unsupported_placement: This profile requires an explicit edge offset. |
| `/default_spec/frame/0/requirement/qty` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/0/requirement/qty` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/frame/0/requirement/length_rule` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/0/requirement/length_rule` | invalid_length_rule: Explicit supported length rule required for this member. |
| `/default_spec/frame/0/requirement/overlap` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/0/requirement/overlap` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/frame/1/joint/shared_host_gap` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/1/joint/gap_reason` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/1/joint/kind` | uncited: Nonempty source citations are required. |
| `/default_spec/frame/1/joint/channel_depth` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/1/joint/channel_depth` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/frame/1/joint/insertion_margin` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/1/joint/insertion_margin` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/frame/1/orientation` | uncited: Nonempty source citations are required. |
| `/default_spec/frame/1/placement` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/1/placement` | unsupported_placement: This profile requires an explicit edge offset. |
| `/default_spec/frame/1/requirement/qty` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/1/requirement/qty` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/frame/1/requirement/length_rule` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/1/requirement/length_rule` | invalid_length_rule: Explicit supported length rule required for this member. |
| `/default_spec/frame/1/requirement/overlap` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/frame/1/requirement/overlap` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/infill/orientation` | uncited: Nonempty source citations are required. |
| `/default_spec/infill/justification` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/justification` | unsupported_fitting: Explicit supported fitting policy required. |
| `/default_spec/infill/excess` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/excess` | unsupported_fitting: Explicit supported fitting policy required. |
| `/default_spec/infill/supply` | uncited: Nonempty source citations are required. |
| `/default_spec/infill/edge_margin` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/edge_margin` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/infill/pattern/0/joint` | missing_joint: Explicit Joint object required. |
| `/default_spec/infill/pattern/0/base_engagement` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/pattern/0/base_engagement` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/infill/pattern/0/top_engagement` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/pattern/0/top_engagement` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/infill/pattern/0/gap_after` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/pattern/0/gap_after` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/infill/pattern/0/face_offset` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/pattern/0/face_offset` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/infill/pattern/0/profile_edges` | uncited: Nonempty source citations are required. |
| `/default_spec/infill/pattern/0/requirement/qty` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/pattern/0/requirement/qty` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/infill/pattern/0/requirement/length_rule` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/pattern/0/requirement/length_rule` | invalid_length_rule: Explicit supported length rule required for this member. |
| `/default_spec/infill/pattern/0/requirement/overlap` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/default_spec/infill/pattern/0/requirement/overlap` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/default_spec/fixings` | missing_value: Explicit fixing list required. |
| `/post/requirement` | missing_requirement: Explicit PartRequirement required. |
| `/post/joint` | missing_joint: Explicit Joint object required. |
| `/post/cap/qty` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/post/cap/qty` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/post/cap/length_rule` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/post/cap/overlap` | missing_value: Explicit authored value required; no consumer default is evidence. |
| `/post/cap/overlap` | invalid_quantity: A cited integer-milli Quantity with raw reading is required. |
| `/` | consumer_numeric_provenance_mapping_unresolved: Numeric model values need published provenance under contract obligation 6; this profile only stores private field citations and has no agreed lossless publication mapping. |

## Assembly work remaining

- Installed board pitch/overlap and explicit end-fitting policy
- Source-supported receiving depths and engagements on each axis
- Rail-to-post engagements at each end and shared-post clearance
- Lossless public geometry/provenance mapping and consumer support
- Mapping public Part receipts to private generation definitions without treating opaque versions as sortable revisions
- Single-panel and multi-panel assembly with shared posts, consistent cuts and component counts

Kit purchasing follows the component BOM; incomplete package contents cannot supply purchase credits.
