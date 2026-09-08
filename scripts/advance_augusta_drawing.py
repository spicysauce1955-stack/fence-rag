"""Import the bounded Augusta readings and publish their source-scoped Parts.

No human reviews are created. Sibling CAD drawings (8x8, gate) and the
specsheet/brochure positional pairing were inspected as run metadata only.
"""
import json
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fence_evidence import augusta_drawing_claims as recipe
from fence_evidence.paths import open_write
from fence_evidence.store import connect
from fence_evidence.snapshot import build_snapshot, verify
from fence_evidence.snapshot_store import put_snapshot

SOURCES=[
    ('manuals/weatherables/structural/weatherables-cad-augusta-8x6-privacy.png',recipe.CAD_SHA),
    ('manuals/weatherables/weatherables-fencing-master-installation-instructions-2024.pdf',recipe.INSTALL_SHA),
    ('manuals/weatherables/weatherables-privacy-fencing-specsheet.pdf',recipe.SPECSHEET_SHA),
]


def main():
    for path,sha in SOURCES:
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:
            raise ValueError('Retained source bytes changed: '+path)
    conn=connect()
    try:
        imported={'cad':recipe.import_cad_readings(conn),'install':recipe.import_install_readings(conn),
            'specsheet':recipe.import_specsheet_readings(conn)}
        snapshot=build_snapshot(tenant='default',conn=conn);verify(snapshot)
        path=put_snapshot(snapshot)
        selected=[p for p in snapshot['parts'] if p['id'].startswith(recipe.PREFIX)]
        report={'scope':'Weatherables Augusta 8x6 privacy CAD drawing plus install-guide and specsheet readings; exact SKU unverified',
            'sources':[{'path':p,'sha256':s} for p,s in SOURCES],'imported':imported,
            'snapshot_id':snapshot['snapshot_id'],'snapshot_path':str(path.relative_to(ROOT)),
            'parts':selected,'human_reviews_created':False,
            'persisted_unpublished':['panel_drawing_overall_width_mm','panel_drawing_overall_height_mm',
                'panel_drawing_picket_run_upper_mm','panel_drawing_picket_run_lower_mm'],
            'remaining_gaps':['Overall panel dimensions and picket-run segments persist as flagged facts; no component Part owns them while FenceModel provenance mapping (Amendment 008) is pending.',
                'Receiving depths, seating, installed pitch and cut allowances are not inferred from the drawing.',
                'Rail count (three) and picket runs are cross-checked against sibling CADs and brochure text, but component interchangeability and exact-SKU identity remain unverified.',
                'No purchasing quantities or kit inventory are claimed.']}
        with open_write(ROOT/'workspace/reports/augusta-drawing-publication.json') as f:
            json.dump(report,f,indent=2);f.write('\n')
        bindings=[]
        rail_keys={'rail_drawing_width_mm':'width_mm','rail_drawing_height_mm':'height_mm',
            'rail_drawing_length_mm':'length_mm'}
        for component,fact_type,anchor,_ in recipe.CAD_READINGS:
            if component=='rail':
                bindings.append({'part_id':recipe.PREFIX+'rail','spec_key':rail_keys[fact_type],
                    'extractor':recipe.CAD_EXTRACTOR,'fact_type':fact_type,'element_id':recipe.CAD_ANCHORS[anchor][0]})
        for component,fact_type,anchor,_ in recipe.INSTALL_READINGS:
            bindings.append({'part_id':recipe.PREFIX+component,'spec_key':'nominal_designation',
                'extractor':recipe.INSTALL_EXTRACTOR,'fact_type':fact_type,'element_id':recipe.INSTALL_ANCHORS[anchor][0]})
        keys={'picket_thickness_in':'nominal_thickness_mm','picket_width_in':'nominal_width_mm'}
        for component,fact_type,anchor,_raw,_n in recipe.SPECSHEET_READINGS:
            bindings.append({'part_id':recipe.PREFIX+component,'spec_key':keys[fact_type],
                'extractor':recipe.SPECSHEET_EXTRACTOR,'fact_type':fact_type,'element_id':recipe.SPECSHEET_ANCHORS[anchor][0]})
        batch={'batch_id':'augusta-drawing-001','profile':'persisted-facts-to-parts-v1','tenant':'default',
            'scope':report['scope'],'sources':[{'path':p,'sha256':s} for p,s in SOURCES],
            'snapshot':str(path.relative_to(ROOT)),
            'part_ids':[recipe.PREFIX+c for c in ('rail','u-channel','picket')],
            'bindings':bindings,
            'implementation_files':['fence_evidence/augusta_drawing_claims.py','fence_evidence/parts.py','fence_evidence/reviews.py','fence_evidence/snapshot.py'],
            'historical_evidence':[],
            'limitations':report['remaining_gaps']+['AI visual CAD readings remain flagged at curation level 0; OCR text is preserved verbatim and was not corrected in canonical storage.']}
        with open_write(ROOT/'workspace/catalog/augusta-conversion-batch.json') as f:
            json.dump(batch,f,indent=2);f.write('\n')
        print(json.dumps({'snapshot_id':snapshot['snapshot_id'],'parts':len(selected),
            'facts':sum(len(v) for v in imported.values())}))
    finally:conn.close()


if __name__=='__main__':main()