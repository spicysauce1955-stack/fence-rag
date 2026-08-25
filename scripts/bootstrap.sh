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
    echo "On Debian/Ubuntu:"
    echo "  sudo apt install poppler-utils tesseract-ocr tesseract-ocr-eng python3"
    echo "On macOS:"
    echo "  brew install poppler tesseract"
    echo "On Fedora:"
    echo "  sudo dnf install poppler-utils tesseract tesseract-langpack-eng"
    echo
    echo "These are external binaries, not Python packages -- there is no pip"
    echo "route to them. The machine this pipeline was built on had no sudo, apt"
    echo "or system pip at all, which is why the only Python dependency is"
    echo "vendored into workspace/pylibs/ rather than installed; see"
    echo "workspace/reports/dependency-options.md."
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
# ------------------------------------------------------------- git lfs ------
# Having the binary is not the same as having the filters. `git lfs install`
# is what writes filter.lfs.* into the git config, and without it git does not
# know what `filter=lfs` in .gitattributes means: it skips the clean filter,
# so `git add --renormalize .` -- the documented way to settle `git status`
# after a fetch -- would stage 376 MB of raw PDF as ordinary blobs instead of
# pointers. That is committable, and unrecoverable once pushed.
bold "Git LFS"
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    ylw "  skipped   not a git checkout"
elif ! command -v git-lfs >/dev/null 2>&1; then
    ylw "  absent    git-lfs is not installed"
    echo "            Not required: 'cli fetch' does not use it. But do NOT run"
    echo "            'git add --renormalize .' without it -- see README.md."
    warnings=$((warnings + 1))
elif [ -n "$(git config --get filter.lfs.clean || true)" ]; then
    grn "  ok        LFS filters configured"
else
    ylw "  absent    git-lfs is installed but 'git lfs install' has never run"
    echo "            Filters are unconfigured, so git treats the corpus PDFs as"
    echo "            ordinary files. Fix before touching the index:"
    echo "              git lfs install           # per machine"
    echo "              git lfs install --local   # or just this repository"
    echo "            Until then do NOT run 'git add --renormalize .' -- it"
    echo "            would stage 376 MB of PDF into git history outside LFS."
    warnings=$((warnings + 1))
fi
echo

bold "Corpus"
# Detect unsmudged LFS pointers by their signature, not by file size. A pointer
# is ~131 bytes, but `find -size -1k` rounds UP to whole blocks, so a pointer
# matches neither -1k nor +1k, both counts come back zero, and the script reports
# "no corpus PDFs" in exactly the situation this check exists to diagnose.
pdfs=0
ptrs=0
while IFS= read -r f; do
    if head -c 42 "$f" 2>/dev/null | grep -q '^version https://git-lfs'; then
        ptrs=$((ptrs + 1))
    else
        pdfs=$((pdfs + 1))
    fi
done < <(find manuals china/manuals -name '*.pdf' 2>/dev/null)
if [ "$pdfs" -gt 0 ] && [ "$ptrs" -eq 0 ]; then
    grn "  ok        $pdfs PDFs present"
    if [ -n "$(git config --get filter.lfs.clean || true)" ] \
       && [ -n "$(git status --porcelain -- manuals china/manuals 2>/dev/null)" ]; then
        ylw "  note      git reports corpus files as modified after a fetch."
        echo "            Their content is correct and 'git diff' is empty; the"
        echo "            index still holds the pointers' stat data. Settle it:"
        echo "              git add --renormalize ."
        echo "            Do NOT 'git checkout' them -- that restores pointers."
    fi
elif [ "$ptrs" -gt 0 ]; then
    ylw "  partial   $pdfs PDFs present, $ptrs still unsmudged LFS pointers"
    echo "            Until they are fetched they are recorded as 'not-fetched',"
    echo "            and ingestion refuses them rather than extracting a stub."
    echo "            Fetch from public object storage -- free, no account, no"
    echo "            LFS bandwidth spent:"
    echo "              python3 -m fence_evidence.cli fetch --subset structural  #  73.5 MB"
    echo "              python3 -m fence_evidence.cli fetch --subset all         # 376.5 MB"
    echo "            Fallback, only if that host is unreachable from here --"
    echo "            it spends a 1 GB/month allowance shared by everyone:"
    echo "              git lfs pull --include='**/structural/**'   # ~109 MB"
else
    ylw "  absent    no corpus PDFs. Extraction will do nothing."
    echo "            python3 -m fence_evidence.cli fetch --subset all"
    echo "            (fallback: git lfs pull --include=<subset>; see README.md)"
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
echo "  python3 -m fence_evidence.cli fetch --subset all      # the corpus, from public storage"
echo "  python3 tests/run_tests.py                            # runs without a corpus; corpus tests skip"
echo "  python3 -m fence_evidence.cli manifest                # inspect the corpus"
echo "  python3 -m fence_evidence.cli ingest --pilot          # 10-document smoke test"
echo "  python3 -m fence_evidence.cli ingest --all            # full corpus, ~33 min"
