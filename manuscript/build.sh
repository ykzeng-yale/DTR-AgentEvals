#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 prepare_bibliography.py
if command -v latexmk >/dev/null 2>&1; then
    latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
else
    # Optional local Tectonic fallback for hosts without a TeX Live installation.
    # Set DTR_TECTONIC_BIN to an absolute path to a verified binary, or use PATH.
    compiler=${DTR_TECTONIC_BIN:-tectonic}
    if ! command -v "$compiler" >/dev/null 2>&1; then
        echo "Need latexmk/pdfLaTeX or Tectonic (DTR_TECTONIC_BIN); see manuscript/README.md." >&2
        exit 1
    fi
    mkdir -p build
    "$compiler" --untrusted --keep-logs --keep-intermediates --outdir build main.tex
fi
cp build/main.pdf DTR_Agent_Regimes_Theory_Draft.pdf
