"""Import the bounded scanned drawing recipe and publish its source-scoped Parts.

No human reviews or exact-SKU component equivalence are created.
"""
import json
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fence_evidence import emblem_drawing_claims as recipe
from fence_evidence.paths import open_write
from fence_evidence.store import connect
from fence_evidence.snapshot import build_snapshot, verify
from fence_evidence.snapshot_store import put_snapshot


def main():
    source='manuals/freedom-outdoor-living/structural/MiamiDade-NOA-22-0217.05-Barrette-Extruded-PVC-Vinyl-Fence.pdf'
    if hashlib.sha256((ROOT/source).read_bytes()).hexdigest()!=recipe.SOURCE_SHA:
        raise ValueError('Retained drawing bytes changed')
    conn=connect()
    try:
        imported=recipe.import_readings(conn)
        snapshot=build_snapshot(tenant='default',conn=conn);verify(snapshot)
        path=put_snapshot(snapshot)
        selected=[p for p in snapshot['parts'] if p['id'].startswith(recipe.PREFIX)]
        report={'scope':'NOA22-0217.05 pre-built Emblem drawing001 sheet4; exact SKU unverified',
            'source_sha256':recipe.SOURCE_SHA,'source_page':7,'imported':imported,
            'snapshot_id':snapshot['snapshot_id'],'snapshot_path':str(path.relative_to(ROOT)),
            'parts':selected,'assembly_validated':False,'human_reviews_created':False,
            'remaining_gaps':['Exact-SKU/revision applicability and reinforced configuration differ from standard RTA instructions.',
                'Receiving depths, usable seats and installed pitch are not inferred from undimensioned profile features.',
                'Inherited document metadata says unspecified/superseded; its classification/lineage needs separate curation.']}
        with open_write(ROOT/'workspace/reports/emblem-drawing-publication.json') as f:
            json.dump(report,f,indent=2);f.write('\n')
        batch={'batch_id':'emblem-drawing-002','profile':'persisted-facts-to-parts-v1','tenant':'default',
            'scope':report['scope'],'sources':[{'path':source,'sha256':recipe.SOURCE_SHA}],
            'snapshot':str(path.relative_to(ROOT)),
            'part_ids':[recipe.PREFIX+c for c in ('rail','board','end-channel')],
            'bindings':[{'part_id':recipe.PREFIX+c,'spec_key':k,'extractor':recipe.EXTRACTOR,
                'fact_type':c.replace('-','_')+'_'+k,'element_id':recipe.ANCHORS[a][0]} for c,k,a,_ in recipe.READINGS],
            'implementation_files':['fence_evidence/emblem_drawing_claims.py','fence_evidence/parts.py','fence_evidence/reviews.py','fence_evidence/snapshot.py'],
            'historical_evidence':[],'limitations':report['remaining_gaps']+['AI visual readings remain flagged at curation level0. No complete fit or purchase validation.']}
        with open_write(ROOT/'workspace/catalog/emblem-drawing-conversion-batch.json') as f:
            json.dump(batch,f,indent=2);f.write('\n')
        print(json.dumps({'snapshot_id':snapshot['snapshot_id'],'parts':len(selected),'facts':len(imported)}))
    finally:conn.close()


if __name__=='__main__':main()
