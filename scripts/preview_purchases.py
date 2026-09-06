"""Generate a private purchase preview from a model package and clean layout."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fence_evidence.paths import EVIDENCE_DB, open_write
from fence_evidence.purchase_preview import generate, PreviewError


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    conn = sqlite3.connect(f'file:{EVIDENCE_DB}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    try:
        result = generate(json.loads(args.model.read_text()), json.loads(args.layout.read_text()), conn=conn)
    except PreviewError as exc:
        print(f'Preview refused: {exc}', file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()
    with open_write(args.output, encoding='utf-8') as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    print(json.dumps({'output': str(args.output),
                      'counts': {x['manufacturer_model_number']: x['quantity_each'] for x in result['purchase_lines']},
                      'source_identity_verified': result['source_identity_verified'],
                      'contract_consumer_verified': False}, indent=2))
