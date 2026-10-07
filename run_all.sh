#!/bin/bash
# Full pipeline: validation runs -> selection of eta -> test runs -> analysis -> figures.
# Usage: bash run_all.sh        (PYTHON=<interpreter> and MEMSTUDY_PROCS=<workers> are optional)
# The runs are resumable: results that are already in results/runs.jsonl are not repeated.
cd "$(dirname "$0")" || exit 1
PY=${PYTHON:-python}
OUT=${MEMSTUDY_RESULTS:-results}
mkdir -p "$OUT" figures

$PY experiments/run_study.py      > "$OUT/run.log" 2>&1      || exit 1
$PY experiments/run_study.py logs > "$OUT/logs.log" 2>&1     || exit 1
$PY experiments/analyze.py        > "$OUT/analyze.log" 2>&1  || exit 1
$PY experiments/make_figures.py   > "$OUT/figures.log" 2>&1  || exit 1
echo "pipeline finished; results in $OUT, figures in figures/"
