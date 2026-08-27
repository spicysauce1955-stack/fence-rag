# PR #2 code-review fix wave — report

Branch: `four-layer-plan-1-refs`, starting HEAD `5731138`. Four commits added, all from repo root.

```
4bbb8d8 cli.py: split the verify diagnosis, and make --verify/--index a real choice
c3628d0 refs.py: verify_snapshots gains three more signals it was blind to
9fc6398 measure_ref_stability.py: import ref_id instead of reimplementing it
560233f Fix the minting join key to match the index's
5731138 (start) Banner the superseded sref_ design, and record G39
```

## FIX 1 (HIGH) — snapshot.py minting join — commit `560233f`

`SnapshotBuilder.source_ref()` joined `document_versions v ON v.document_id = e.document_id`
then `.fetchone()`, matching whichever version row SQLite returned first rather than the
element's own version — while `refs.build_index` already joins on `v.version_id = e.version_id`.
Changed the join to `v.version_id = e.version_id` and added a comment pointing at
`refs.build_index`'s matching comment.

**Byte-identity proof (verbatim):**

```
$ python3 -c "
import json, glob, sys
sys.path.insert(0, '.')
from fence_evidence.snapshot import build_snapshot
built = build_snapshot(tenant='acme', regime='us_astm')
onfile = json.load(open(glob.glob('workspace/snapshots/*.json')[0]))
b = {c['id'] for w in built.get('warnings', []) for c in w.get('cites', [])}
o = {c['id'] for w in onfile.get('warnings', []) for c in w.get('cites', [])}
print('cites built:', len(b), 'cites on file:', len(o))
print('snapshot_id built:', built['snapshot_id'])
print('snapshot_id on file:', onfile['snapshot_id'])
print('IDENTICAL' if b == o and built['snapshot_id'] == onfile['snapshot_id'] else 'DIFFER')
"
cites built: 431 cites on file: 431
snapshot_id built: 02a8833be1f0da2048b039e4e42a5c81de8fba2b4851d5e12c7662d14d43ceac
snapshot_id on file: 02a8833be1f0da2048b039e4e42a5c81de8fba2b4851d5e12c7662d14d43ceac
IDENTICAL
```

**FIX 1 VERDICT: IDENTICAL, 431/431, matching snapshot_ids. Not blocked.**

`workspace/snapshots/` md5 confirmed unchanged before and after (this script only calls
`build_snapshot`, never `put_snapshot`, so nothing was written): `67188296dc37d6e11c66d23203320297`.

## FIX 2 (MEDIUM) — CLI misdiagnosis on a partial store — commit `4bbb8d8`

`verify_snapshots`'s `unknown_versions` list already names every cite whose `belongs_to` is
not a known version. In `cli.py`'s `refs --verify` branch, cross-referenced `dangling` against
`unknown_versions` by `ref_id`:

```python
unknown_ref_ids = {u["ref_id"] for u in result["unknown_versions"]}
rot = [d for d in result["dangling"] if d["ref_id"] not in unknown_ref_ids]
```

`rot` (dangling *and* the cited version IS present) gets the "genuine rot ... cannot be
repaired ... see docs/four-layer-model-design.md 5.1" message. `unknown_versions` (whether or
not the same cite is also dangling) gets a separate message pointing at `cli fetch` /
`cli ingest --all`. Both still exit 1. `mismatched_owner` and `unreadable` (added in the
previous commit) are now also gated with their own messages, `mismatched_owner` keeping the
5.1 pointer since it is also genuine, irreparable rot.

Verified against a fabricated in-memory store + temp snapshot dir: a cite whose `belongs_to`
names an unknown version lands only in the "incomplete store" bucket, not "genuine rot" (shown
inline in the session, not added as a permanent test — no `tests/test_cli.py` exists in this
repo and FIX 2/6 were not in the explicit test-required list).

## FIX 3 (MEDIUM) — measure_ref_stability.py reimplementing ref_id — commit `9fc6398`

Removed `_h()` (a second `hashlib.sha256(...).hexdigest()[:16]`), imported
`from fence_evidence.refs import ref_id`, and rewrote every call site to the 3-argument form.
The two "alternative identity scheme" lambdas (`sha:page:text`, `sha:page:type:text`) are not
the `ref_id` formula — they hash different content — but reuse `ref_id` by folding the extra
field(s) into its third (`bbox`-shaped, passed through verbatim) argument, which produces byte-
identical hashes to the original string concatenation.

**Script output before and after — identical:**

```
1. hash sensitivity to a 0.02pt bbox shift (1/3600 inch)
   [117.69, 271.47, 266.99, 294.03] -> cd9f0d9d9c4e300f
   [117.69, 271.47, 266.99, 294.05] -> e25f68cec20de1bc

2. index over 81794 elements: 69306 distinct ids in 75 ms, 0 true collisions

3. alternative identity schemes
   sha:page:bbox (shipped)      69306 distinct    22418 elements share an id
   sha:page:text                56090 distinct    38602 elements share an id
   sha:page:type:text           56442 distinct    37969 elements share an id
   elements with no text at all: 6660

4. kind collisions (a bbox-less element ref == its page ref): 416
   15d1ceaf5cb24da2 = element element-e41aee54e9-0000 (heading, bbox=None) AND page 1
   15d1ceaf5cb24da2 = element element-e41aee54e9-0001 (heading, bbox=None) AND page 1
   15d1ceaf5cb24da2 = element element-e41aee54e9-0002 (heading, bbox=None) AND page 1
   ids covering more than one element: 9929
```

All six numbers match the required 81794 / 69306 / 0 / 56090 / 6660 / 416 / 9929.

`grep -rn "def ref_id" fence_evidence/` → exactly one hit (`fence_evidence/refs.py:45`).

## FIX 4 (LOW) — mismatched_owner check — commit `c3628d0`

In `refs.verify_snapshots`, once a cite resolves to a `Locus`, compare `locus.sha256` against
the cite's own `belongs_to`:

```python
if owner and locus.sha256 != owner:
    out["mismatched_owner"].append({...})
```

Added to the result dict (list, same entry shape as `dangling` plus a `reason`). Does not
change `resolved` counting — a mismatched-owner cite still resolves, it just also gets flagged.
Two new tests: `TestVerifyMismatchedOwner.test_a_valid_id_with_the_wrong_belongs_to_is_reported`
and `.test_an_honestly_owned_cite_is_not_flagged`, both against a fabricated in-memory store.
Measured: 0 mismatches on the real store (confirmed by `refs --verify` output above).

## FIX 5 (LOW) — resolved_as_page_only signal — commit `c3628d0`

Added `resolved_as_page_only` (an int count, not a list) for resolved cites whose `Locus` has
`is_page=True` and empty `element_ids` — a citation that will resolve forever even after every
element it named is deleted, because the `pages` row backing the id never goes away. Not gated
as a failure (per spec — "watch it", not an error). Docstring explains why it matters (the
§5.2 `kind` defect showing up in the guard, plan 2's work). Two new tests:
`TestVerifyResolvedAsPageOnly.test_a_pure_page_ref_is_counted_separately_from_resolved` and
`.test_a_cite_backed_by_an_element_is_not_page_only`. Measured: 0 on the real store today.

## FIX 6 (LOW) — dead `--index` flag — commit `4bbb8d8`

Dispatch was `if args.verify: ... else: build_index(...)`. Changed to require exactly one of
`--verify` / `--index`:

```python
if args.verify == args.index:
    _print({"error": "choose one of --verify, --index"})
    return 0
```

(True when neither or both are set — both booleans.) Mirrors `snapshot`'s existing
`{"error": "choose one of --build, --dry-run, --list, --get"}` shape and voice, including its
exit-0 behavior on that branch (matched deliberately — fixing that pre-existing quirk was out
of scope; it isn't mentioned in the finding). Verified: bare `cli refs` and
`cli refs --verify --index` both now print the choose-one-of error instead of silently picking
a branch; `cli refs --verify` and `cli refs --index` alone are unaffected.

## FIX 7 (LOW) — unguarded JSON parse — commit `c3628d0`

Wrapped the per-file read in `refs.verify_snapshots`:

```python
try:
    payload = json.loads(snap_path.read_bytes())
    if not isinstance(payload, dict):
        raise TypeError(f"expected a JSON object at the top level, got {type(payload).__name__}")
except (json.JSONDecodeError, TypeError, UnicodeDecodeError) as exc:
    out["unreadable"].append({"file": snap_path.name, "reason": str(exc)})
    continue
```

Added `unreadable` (list) to the result dict; verification continues over the remaining files.
Gated in the CLI's exit-1 condition with its own message. Two new tests:
`TestVerifyUnreadable.test_a_corrupt_json_file_is_recorded_not_raised` (a hand-corrupted
`.json` alongside a good snapshot — confirms the good one is still verified) and
`.test_a_non_object_payload_is_recorded_not_raised` (a JSON list at the top level).

## Test counts

- Before this wave: `python3 tests/run_tests.py` → **447 tests, 5 skips, OK**.
- After this wave: `python3 tests/run_tests.py` → **453 tests, 5 skips, OK** (6 new tests: 2
  each for mismatched_owner, resolved_as_page_only, unreadable). New classes
  (`TestVerifyMismatchedOwner`, `TestVerifyResolvedAsPageOnly`, `TestVerifyUnreadable`) were
  added to `tests/test_refs.py` above its `if __name__ == "__main__":` guard.
- `cd tests && python3 -m unittest test_refs -v` → 30/30 ok, individually confirmed.

## Full acceptance check (final state)

```
$ python3 tests/run_tests.py 2>&1 | tail -5
Ran 453 tests in 14.711s
OK (skipped=5)

$ python3 -m fence_evidence.cli refs --verify
{
  "snapshots": 1, "tombstoned_skipped": 0, "cites": 431, "resolved": 431,
  "resolved_as_page_only": 0, "dangling": [], "unknown_versions": [],
  "mismatched_owner": [], "unreadable": []
}
EXIT:0

$ python3 -m fence_evidence.cli refs --index
{"ref_ids": 71158, "page_refs": 1853, "ids_covering_multiple_elements": 9930}

$ python3 scripts/measure_ref_stability.py
-> 81794 / 69306 / 0 / 56090 / 6660 / 416 / 9929   (all six numbers match)

$ grep -rn "def ref_id" fence_evidence/
fence_evidence/refs.py:45:def ref_id(...)   # exactly one hit

$ grep -n "SCHEMA_VERSION = " fence_evidence/store.py
22:SCHEMA_VERSION = 3

$ git diff origin/four-layer-plan-1-refs -- fence_evidence/store.py | wc -l
0

$ md5sum workspace/snapshots/*.json
67188296dc37d6e11c66d23203320297  workspace/snapshots/02a8833be1f0da2048b039e4e42a5c81de8fba2b4851d5e12c7662d14d43ceac.json
```

All acceptance criteria hold. No document under `docs/integration/`, `AGENTS.md`,
`workspace/derived/visualization-tools/`, `manuals/`, `china/manuals/`, or `data/` was touched.
No `cli snapshot --build`/`--dry-run` was run. No `git lfs pull` was run. No bare `open(...,
"w")` was used — the only writes were the new report file and normal source edits via the
Edit tool.

## Concerns / judgment calls worth flagging

1. **FIX 6 exit code.** `snapshot`'s own "choose one of" branch falls through to the function's
   final `return 0` — i.e. it exits 0 on a usage error. I mirrored that exactly for `refs`
   (`return 0`) per "match snapshot's existing error shape and voice," rather than making `refs`
   stricter (`return 1`) than its sibling. This is arguably a latent bug in both commands (a
   misconfigured invocation exits green), but fixing it wasn't asked for and isn't scoped to
   this finding — flagging in case the reviewer actually wanted `refs` to exit 1 here, which
   would be a one-line change (`return 0` → `return 1`) if desired.
2. **FIX 2 message scope.** `unknown_versions` entries are reported once as a whole (not split
   further into "also dangling" vs "resolved-but-bad-owner" subcases) — the `rot` bucket
   subtracts anything explained by `unknown_versions`, but the `unknown_versions` message itself
   covers all of them, dangling or not. This matches the finding's literal ask ("split the CLI's
   message" using `unknown_versions` as "the distinguishing signal") without inventing an
   unrequested third category; a resolved-but-bad-`belongs_to` cite (0 today) would print both
   the `unknown_versions` message and, if the owner mismatch is also non-empty, the
   `mismatched_owner` message.
3. **FIX 3 reuse of `ref_id` for non-canonical schemes.** The two comparison schemes in
   `measure_ref_stability.py §3` (`sha:page:text`, `sha:page:type:text`) now call `ref_id()`
   with extra fields folded into its `bbox` parameter. This is numerically exact (`ref_id` just
   interpolates its third argument verbatim into the hash input) but is a slightly unusual reuse
   of a function whose contract is "an evidence locator." Commented in the diff to make the
   intent explicit; happy to instead keep a small local generic-hash helper for those two lines
   only if that reads better to the reviewer — I judged full `_h` removal (literally: "use it
   everywhere `_h` is currently called") to be the more faithful reading of the finding.

## Corrections (round 2)

The coordinator confirmed both flagged concerns were real bugs, not judgment calls to leave as
documented, and asked for both to be corrected in one commit.

### CORRECTION A — `cli.py` refs usage-error branch must not exit 0

Changed the branch in `fence_evidence/cli.py`'s `refs` dispatch:

```python
if args.verify == args.index:
    _print({"error": "choose one of --verify, --index"})
    return 2
```

(was `return 0`, mirroring `snapshot`'s own sibling branch, which is itself G39's pre-existing
defect). `refs --verify` is a CI guard; a usage error printing to stdout with a green exit is
the exact vacuous-green failure class FIX 5's `resolved_as_page_only`/the "0 snapshots found"
check exist to prevent, so it now exits `2` (argparse's usage-error convention, distinct from
`1` = "the guard fired and found rot"). `snapshot`'s own branch was deliberately left
**unchanged** — still exits 0 on `snapshot --build --dry-run`'s sibling case — because that is
the pre-existing, separately-scoped G39 defect, not this finding.

Added a note to G39 in `docs/state-and-gaps.md` (in its existing voice) recording `refs`'s
branch as "a second, related instance" of the same "usage error exits 0" shape, explaining why
it was corrected here while `snapshot`'s was not, and pointing at the same deferred
`add_mutually_exclusive_group()` fix for `snapshot`.

Added `TestCLIRefsDispatch` to `tests/test_refs.py` (calls `fence_evidence.cli.main([...])`
directly, capturing stdout): `test_neither_flag_exits_nonzero` and
`test_both_flags_exits_nonzero`, both asserting `code != 0` and that the "choose one of" message
appears in stdout.

Verified:

```
$ python3 -m fence_evidence.cli refs; echo "EXIT:$?"
{"error": "choose one of --verify, --index"}
EXIT:2
$ python3 -m fence_evidence.cli refs --verify --index; echo "EXIT:$?"
{"error": "choose one of --verify, --index"}
EXIT:2
$ python3 -m fence_evidence.cli snapshot; echo "EXIT:$?"
{"error": "choose one of --build, --dry-run, --list, --get"}
EXIT:0        # unchanged, deliberately
```

### CORRECTION B — `measure_ref_stability.py` must not pass text through `ref_id`'s bbox slot

Reverted the two comparison-scheme lambdas (`"sha:page:text"`, `"sha:page:type:text"`) from
calling `ref_id(...)` with normalised text folded into its `bbox` argument, back to a small
local helper:

```python
def _alt_hash(s: str) -> str:
    """A counterfactual identity scheme's hash -- deliberately NOT ref_id. ..."""
    return hashlib.sha256(s.encode()).hexdigest()[:16]
```

used as `_alt_hash(f"{sha256}:{page_no}:{norm(body)}")` and
`_alt_hash(f"{sha256}:{page_no}:{element_type}:{norm(body)}")`. The shipped scheme's row
(`"sha:page:bbox (shipped)"`), and sections 1, 2, and 4 (all real ref_ids), still call `ref_id`
directly — FIX 3's actual requirement (no second copy of the *shipped* formula) stands. `_h` is
still gone entirely; `_alt_hash` is a distinctly-named, clearly-commented, single-purpose helper
for content `ref_id` was never meant to hash, not a re-implementation of `ref_id` itself.

Verified: `grep -rn "def ref_id" fence_evidence/` still exactly one hit (only in
`fence_evidence/refs.py`); the two comparison-scheme numbers are unchanged (56090 distinct /
38602 shared, and 56442 distinct / 37969 shared) because `_alt_hash` hashes the identical
input string the original `_h` did.

### Final verification after both corrections

```
$ python3 tests/run_tests.py 2>&1 | tail -5
Ran 455 tests in 14.435s
OK (skipped=5)

FIX 1 byte-identity proof:
cites built: 431 cites on file: 431
snapshot_id built: 02a8833be1f0da2048b039e4e42a5c81de8fba2b4851d5e12c7662d14d43ceac
snapshot_id on file: 02a8833be1f0da2048b039e4e42a5c81de8fba2b4851d5e12c7662d14d43ceac
IDENTICAL

$ python3 -m fence_evidence.cli refs --verify
{"snapshots": 1, "tombstoned_skipped": 0, "cites": 431, "resolved": 431,
 "resolved_as_page_only": 0, "dangling": [], "unknown_versions": [],
 "mismatched_owner": [], "unreadable": []}
EXIT:0

$ python3 -m fence_evidence.cli refs --index
{"ref_ids": 71158, "page_refs": 1853, "ids_covering_multiple_elements": 9930}

$ python3 scripts/measure_ref_stability.py
-> 81794 / 69306 / 0 / 56090 / 6660 / 416 / 9929   (every number unchanged)

$ grep -rn "def ref_id" fence_evidence/
fence_evidence/refs.py:45:def ref_id(...)   # exactly one hit

$ grep -n "SCHEMA_VERSION = " fence_evidence/store.py
22:SCHEMA_VERSION = 3

$ git diff origin/four-layer-plan-1-refs -- fence_evidence/store.py | wc -l
0

$ md5sum workspace/snapshots/*.json
67188296dc37d6e11c66d23203320297  workspace/snapshots/02a8833be1f0da2048b039e4e42a5c81de8fba2b4851d5e12c7662d14d43ceac.json
```

`CLAUDE.md` was checked (lines 103-104, 271): both show single-flag usage examples only, make
no claim about exit codes on a usage error or the dual-flag case, and are not contradicted by
either correction — left unchanged. Both concerns from the original report are now resolved;
no new concerns identified.
