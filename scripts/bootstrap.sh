#!/usr/bin/env bash
# Prepare a fresh checkout so the pipeline runs as documented.
#
# Checks the external prerequisites by name, vendors the one optional Python
# package into workspace/pylibs/, and verifies it imports. Idempotent: a second
# run transfers nothing and changes nothing.
#
# Nothing here writes outside workspace/. Deleting workspace/pylibs/ fully
# reverts the install.
set -uo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
PYLIBS="$REPO_ROOT/workspace/pylibs"

# The toolchain every published measurement was produced on. A mismatch is not
# an error -- it is a warning, because re-extraction is not reproducible across
# tool versions and the numbers in docs/ would no longer be comparable.
REF_POPPLER="24.02.0"
REF_TESSERACT="5.3.4"
PDFPLUMBER_VERSION="0.11.10"

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
grn()  { printf '\033[32m%s\033[0m\n' "$*"; }
ylw()  { printf '\033[33m%s\033[0m\n' "$*"; }
bold() { printf '\033[1m%s\033[0m\n' "$*"; }

missing=()
warnings=0

bold "fence-rag bootstrap"
echo "repo: $REPO_ROOT"
echo

# ---------------------------------------------------------------- python ----
bold "Python"
if ! command -v python3 >/dev/null 2>&1; then
    missing+=("python3 (3.10 or newer)")
else
    pyver="$(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'; then
        grn "  ok        python3 $pyver"
    else
        red "  too old   python3 $pyver (need 3.10+)"
        missing+=("python3 3.10 or newer")
    fi
fi
echo

# --------------------------------------------------------------- poppler ----
bold "poppler (PDF text, page rendering, page geometry)"
for tool in pdftotext pdftoppm pdfinfo; do
    if command -v "$tool" >/dev/null 2>&1; then
        v="$("$tool" -v 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
        v="${v:-unknown}"
        if [ "$v" = "$REF_POPPLER" ]; then
            grn "  ok        $tool $v"
        else
            ylw "  ok        $tool $v  (reference toolchain is $REF_POPPLER)"
            warnings=$((warnings + 1))
        fi
    else
        red "  MISSING   $tool"
        missing+=("$tool (install the 'poppler-utils' package)")
    fi
done
echo

# ------------------------------------------------------------- tesseract ----
bold "tesseract (OCR for the 514 pages with no usable text layer)"
if command -v tesseract >/dev/null 2>&1; then
    tver="$(tesseract --version 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
    tver="${tver:-unknown}"
    if [ "$tver" = "$REF_TESSERACT" ]; then
        grn "  ok        tesseract $tver"
    else
        ylw "  ok        tesseract $tver  (reference toolchain is $REF_TESSERACT)"
        warnings=$((warnings + 1))
    fi
    if tesseract --list-langs 2>&1 | grep -qx "eng"; then
        grn "  ok        tessdata 'eng' present"
    else
        red "  MISSING   tessdata 'eng'"
        missing+=("tesseract English data (install 'tesseract-ocr-eng')")
    fi
else
    red "  MISSING   tesseract"
    missing+=("tesseract (install the 'tesseract-ocr' package)")
fi
echo

# -------------------------------------------------- hard prerequisite gate ---
if [ ${#missing[@]} -gt 0 ]; then
    red "Cannot continue. Missing prerequisites:"
    for m in "${missing[@]}"; do echo "  - $m"; done
    echo
    echo "This machine has no sudo, apt or system pip by design; see"
    echo "workspace/reports/dependency-options.md for how that shaped these choices."
    exit 1
fi

# --------------------------------------------------------------- pylibs -----
bold "Optional extraction backend (pdfplumber -> workspace/pylibs/)"
echo "  Without it the pipeline still runs, but table extraction silently"
echo "  degrades to the 'fallback-whitespace' backend."
echo

if PYTHONPATH="$PYLIBS" python3 -c "import pdfplumber" >/dev/null 2>&1; then
    have="$(PYTHONPATH="$PYLIBS" python3 -c 'import pdfplumber; print(pdfplumber.__version__)' 2>/dev/null)"
    grn "  ok        pdfplumber $have already vendored"
else
    ylw "  absent    vendoring pdfplumber $PDFPLUMBER_VERSION"
    mkdir -p "$PYLIBS"
    pipz="$(mktemp -d)/pip.pyz"
    echo "            fetching pip zipapp"
    if ! curl -fsSL -o "$pipz" https://bootstrap.pypa.io/pip/pip.pyz; then
        red "  FAILED    could not download pip.pyz (no network?)"
        echo "            Vendor it manually, then re-run:"
        echo "            python3 pip.pyz install --target workspace/pylibs pdfplumber==$PDFPLUMBER_VERSION"
        exit 1
    fi
    echo "            installing into workspace/pylibs/ (nothing touches site-packages)"
    if ! python3 "$pipz" install --quiet --target "$PYLIBS" "pdfplumber==$PDFPLUMBER_VERSION"; then
        red "  FAILED    pip install into workspace/pylibs/ failed"
        exit 1
    fi
    if PYTHONPATH="$PYLIBS" python3 -c "import pdfplumber" >/dev/null 2>&1; then
        have="$(PYTHONPATH="$PYLIBS" python3 -c 'import pdfplumber; print(pdfplumber.__version__)')"
        grn "  ok        pdfplumber $have vendored"
    else
        red "  FAILED    pdfplumber installed but does not import"
        exit 1
    fi
fi
echo

# ---------------------------------------------------------------- corpus ----
bold "Corpus"
pdfs="$(find manuals china/manuals -name '*.pdf' -size +1k 2>/dev/null | wc -l)"
ptrs="$(find manuals china/manuals -name '*.pdf' -size -1k 2>/dev/null | wc -l)"
if [ "$pdfs" -gt 0 ] && [ "$ptrs" -eq 0 ]; then
    grn "  ok        $pdfs PDFs present"
elif [ "$ptrs" -gt 0 ]; then
    ylw "  partial   $pdfs PDFs present, $ptrs still unsmudged LFS pointers"
    echo "            Fetch only what you need -- a full clone costs ~432 MB of a"
    echo "            1 GB/month allowance shared by everyone. See README.md:"
    echo "            git lfs pull --include='**/structural/**'   # ~109 MB"
else
    ylw "  absent    no corpus PDFs. Extraction will do nothing."
    echo "            GIT_LFS_SKIP_SMUDGE=1 clone? Then: git lfs pull --include=<subset>"
fi
echo

# ----------------------------------------------------------------- ready ----
if [ "$warnings" -gt 0 ]; then
    ylw "Ready, with $warnings toolchain difference(s) from the reference environment."
    echo "Extraction is not byte-reproducible across tool versions, so numbers you"
    echo "measure locally may not match those published in docs/state-and-gaps.md."
else
    grn "Ready. Toolchain matches the reference environment."
fi
echo
echo "Next:"
echo "  python3 tests/run_tests.py                            # 164 tests, no corpus needed"
echo "  python3 -m fence_evidence.cli manifest                # inspect the corpus"
echo "  python3 -m fence_evidence.cli ingest --pilot          # 10-document smoke test"
echo "  python3 -m fence_evidence.cli ingest --all            # full corpus, ~33 min"
