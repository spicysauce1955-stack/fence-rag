"""Refusal boundary for Emblem's still-unsupported private consumer mapping.

This is not a published-contract adapter. It exposes why passing the private
parser cannot authorize a component BOM. Capability gaps cannot be cleared by
setting booleans on an authored candidate.
"""
from copy import deepcopy


MODEL_ID = "mfr/freedom-outdoor-living-emblem-73014714"
CONSUMER_REVISION = "9de94eb06d8e997d9be098dedd5b6a6b2eb4024d"


class AdaptationRefused(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__("Emblem consumer adaptation refused: " + "; ".join(
            issue["message"] for issue in report["issues"]))


def _lost_paths(authored, parsed, path=""):
    """Report dropped fields anywhere, including otherwise accepted variants."""
    if isinstance(authored, dict) and isinstance(parsed, dict):
        for key, value in authored.items():
            child = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in parsed:
                yield child
            else:
                yield from _lost_paths(value, parsed[key], child)
    elif isinstance(authored, list) and isinstance(parsed, list):
        for index, value in enumerate(authored):
            child = path + "/" + str(index)
            if index >= len(parsed):
                yield child
            else:
                yield from _lost_paths(value, parsed[index], child)


def probe_engine_capabilities():
    """Execute synthetic resolve and demand cases in the imported consumer.

    These fixture dimensions establish software behavior, never Emblem facts.
    """
    result = {"executed": False, "handed_geometry": False,
              "drawn_purchase_credits": False, "fixture_is_product_evidence": False}
    try:
        from fenceai.fencemodel.model import (FenceModel, FrameSlot, FromBottom,
            PartRequirement, FixingRule, PanelSpec, InfillSpec, Member)
        from fenceai.fencemodel.resolve import PanelContext, resolve_panel
        from fenceai.parts.model import ContainedPart
        from fenceai.strategy.model import Strategy, Span
        from fenceai.demand.derive import derive_requirements
        from fenceai.catalog.model import Catalog
        spec = PanelSpec(
            frame=[FrameSlot(key="rail", orientation="horizontal",
                placement=FromBottom(offset_mm=10),
                requirement=PartRequirement(part_id="synthetic/rail", qty=1,
                                            length_rule="panel_height"))],
            infill=InfillSpec(orientation="vertical", justification="start", excess="truncate",
                pattern=[Member(key="board", width_mm=100,
                    profile_edges={"start": "tongue", "end": "groove"},
                    requirement=PartRequirement(role="infill", qty=1))]),
            fixings=[FixingRule(key="kit", basis="per_panel", qty_per_basis=1,
                requirement=PartRequirement(role="kit", qty=1, geometry_credits=True,
                    contained=[ContainedPart(key="rail", part_id="synthetic/rail", qty=1,
                                             stock_length_mm=100)], credits={"rail": "rail"})),
                *[FixingRule(key=position, basis="per_panel", qty_per_basis=1,
                    edge_binding={"member_key": "board", "position": position, "profile_edge": edge},
                    requirement=PartRequirement(role="end_channel", qty=1))
                  for position, edge in (("first", "tongue"), ("last", "groove"))]])
        panel = resolve_panel(spec, PanelContext(centre_width_mm=500, clear_width_mm=500, height_mm=100))
        slots = {slot.slot_key: slot for slot in panel.slots}
        result["executed"] = True
        result["handed_geometry"] = (slots["first"].bound_position_mm == 0
            and slots["last"].bound_position_mm == 500
            and slots["board"].profile_edges.start == "tongue")
        strategy = Strategy(id="synthetic", spans=[Span(id="span", run_ref="run",
            start_station_mm=0, end_station_mm=500, width_mm=500, slope_len_mm=500, panel=panel)])
        demand = derive_requirements(strategy, Catalog())
        result["drawn_purchase_credits"] = (slots["rail"].qty == 1
            and slots["rail"].purchase_qty == 0 and slots["kit/rail"].qty == 0
            and not any(line.slot_key == "rail" for line in demand)
            and sum(line.engineering_qty for line in demand if line.slot_key == "kit") == 1)
    except (ImportError, ValueError, TypeError, AttributeError, KeyError) as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
    return result


def inspect_candidate(candidate, consumer_model_type=None):
    """Diagnose a private candidate; never claim publication or BOM readiness.

Pass the real consumer FenceModel class to execute its parser. No imports or
checkout paths are imposed on the evidence system. Exact Part selection and
source admission require a reviewed library/catalog and are not asserted here.
    """
    report = {"adapter_implemented": False, "ready": False,
              "consumer_reference_revision": CONSUMER_REVISION,
              "parser_executed": False, "parser_accepts": False,
              "semantic_validation_executed": False,
              "issues": [], "unconsumed_paths": []}

    def issue(code, path, message):
        report["issues"].append({"code": code, "path": path, "message": message})

    if not isinstance(candidate, dict) or not isinstance(candidate.get("model"), dict):
        issue("invalid_shape", "/model", "Expected a private candidate with an object model.")
        return report
    model = candidate["model"]
    if model.get("id") != MODEL_ID:
        issue("wrong_model", "/model/id", "This boundary only describes exact Emblem SKU 73014714.")
        return report
    # Test executable behavior; authored booleans cannot assert capabilities.
    capabilities = probe_engine_capabilities() if consumer_model_type is not None else {}
    report["capability_probe"] = capabilities
    if not capabilities.get("handed_geometry"):
        issue("unsupported_handed_geometry", "/model/default_spec/infill",
          "Executable tongue/groove edge and handed placement support has not passed the capability probe.")
    if not capabilities.get("drawn_purchase_credits"):
        issue("unsupported_kit_geometry_credit", "/model/default_spec",
          "Drawn-member kit purchase credits have not passed the resolve/demand capability probe.")
    issue("publication_adapter_missing", "/model",
          "No reviewed public FenceModel-to-consumer adapter is implemented by this diagnostic.")
    issue("source_admission_unverified", "/model",
          "Exact dimensions, selection, fitting and quantity evidence require reviewed source admission and a complete Part library/catalog.")
    spec = model.get("default_spec")
    if not isinstance(spec, dict):
        issue("invalid_shape", "/model/default_spec", "PanelSpec must be an object.")
        spec = {}
    frame = spec.get("frame")
    if not isinstance(frame, list) or not frame:
        issue("empty_frame", "/model/default_spec/frame", "Emblem requires explicit frame slots.")
        frame = []
    for index, slot in enumerate(frame):
        path = f"/model/default_spec/frame/{index}"
        if not isinstance(slot, dict):
            issue("invalid_shape", path, "Frame slot must be an object.")
            continue
        for key in ("placement", "joint", "channel_depth_mm", "insertion_margin_mm"):
            if key not in slot:
                issue("missing_explicit_value", path + "/" + key, f"Frame {key} must not come from a parser default.")
        depth = slot.get("channel_depth_mm")
        if type(depth) is not int or depth <= 0:
            issue("invalid_channel_depth", path + "/channel_depth_mm", "Channel depth must be a sourced positive integer millimetre projection.")
        _require_quantity(slot.get("requirement"), path + "/requirement", issue)
    infill = spec.get("infill")
    if not isinstance(infill, dict):
        issue("invalid_shape", "/model/default_spec/infill", "Emblem requires an infill object.")
        infill = {}
    for key in ("justification", "excess", "edge_margin_mm", "supply"):
        if key not in infill:
            issue("missing_fitting_rule", "/model/default_spec/infill/" + key, f"Infill {key} requires explicit authoring.")
    pattern = infill.get("pattern")
    if not isinstance(pattern, list) or not pattern:
        issue("empty_infill", "/model/default_spec/infill/pattern", "Emblem requires a board pattern.")
        pattern = []
    for index, member in enumerate(pattern):
        path = f"/model/default_spec/infill/pattern/{index}"
        if not isinstance(member, dict):
            issue("invalid_shape", path, "Infill member must be an object.")
            continue
        req = member.get("requirement")
        _require_quantity(req, path + "/requirement", issue)
        if not isinstance(req, dict) or req.get("length_rule") != "between_frame":
            issue("missing_board_length_rule", path + "/requirement/length_rule", "Rail-supported Emblem boards require between_frame length calculation.")
        for key in ("base_engagement_mm", "top_engagement_mm", "gap_after_mm"):
            if key not in member:
                issue("missing_explicit_value", path + "/" + key, f"Board {key} must not come from a parser default.")
    if consumer_model_type is not None:
        report["parser_executed"] = True
        try:
            parsed = consumer_model_type.model_validate(deepcopy(model))
            report["parser_accepts"] = True
            report["unconsumed_paths"] = list(_lost_paths(model, parsed.model_dump()))
            if report["unconsumed_paths"]:
                issue("unconsumed_authored_fields", "/model", "Parser discards authored fields; an adapter must preserve provenance and implement or refuse behavioral fields.")
        except (ValueError, TypeError, AttributeError) as exc:
            issue("parser_refusal", "/model", str(exc))
    return report


def _require_quantity(requirement, path, issue):
    if not isinstance(requirement, dict):
        issue("invalid_shape", path, "PartRequirement must be an object.")
    elif type(requirement.get("qty")) is not int or requirement["qty"] <= 0:
        issue("missing_explicit_quantity", path + "/qty", "Part quantity must be an explicit positive integer, not a parser default.")


def adapt_candidate(candidate, consumer_model_type=None):
    """Fail closed until an executable, evidence-preserving adapter exists."""
    raise AdaptationRefused(inspect_candidate(candidate, consumer_model_type))
