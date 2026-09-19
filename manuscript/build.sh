#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 prepare_bibliography.py
latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build main.tex
cp build/main.pdf DTR_Agent_Regimes_Theory_Draft.pdf
