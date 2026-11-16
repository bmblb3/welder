# weldfinder

Finds candidate weld curves (edge of one sheet-metal solid near a face of another) and pushes
**one** of them into the CATIA V5 document you have open. Candidates are *geometric proximity*,
not confirmed weld intent. Units: mm.

## Workflow (Windows)
1. Open the STEP in CATIA, hide the bodies you don't care about.
2. Run `weldfinder.exe` (or `weldfinder catia`). It attaches to the running CATIA, reads which
   bodies are visible, loads the STEP geometry, detects candidates among visible solids, and
   creates a geometrical set `WeldCandidate_<id>_<src>_to_<tgt>` with a polyline (straight edge ->
   line) in the active part. Use `--rank N` to push the Nth-best instead, `--dry-run` to only print.
3. Inspect it in CATIA. Re-run with `--rank 1`, `2`, ... for the next ones.

"Best" = longest candidate, weighted by the share of samples whose nearest point is inside a
target face (not on its boundary).

## Install / test (any OS: detection + tests; CATIA bridge needs Windows)
    python -m venv .venv && .venv/bin/pip install -e .[dev]    # Windows: .venv\Scripts\pip
    .venv/bin/pytest
    weldfinder detect model.stp --max-gap 5 --output candidates.json   # offline, all candidates

## Build the .exe (on Windows)
    build_exe.bat      ->  dist\weldfinder.exe

## Key assumptions & limitations (read before trusting results)
* **CATIA bridge is untested against real CATIA** (written from API docs, no CATIA in dev env).
  Most likely first-run fixes: `GetShow` return handling, `HybridShapePolyline` availability,
  how the STEP document is named/located (`find_step_file`; falls back to `ExportData`).
* CATIA bodies are matched to STEP solids by name, else by order if counts agree, else ALL solids
  are used (printed). A CATIA STEP export you do yourself may name things differently from the
  file you imported.
* Assumes CATIA model coordinates == STEP coordinates (no assembly repositioning).
* A plate end typically yields two candidates (one per side of the thickness); both are real.
* Heuristics: tangent-continuous edges, seam edges and short edges (<`--min-length`) are skipped;
  edges whose gap changes by more than max_gap/2 along the run (running toward the face) are
  rejected. Angled flanges with steep gap gradients may be missed; weld intent is never judged
  and legitimate flow openings are not distinguished.
* Curves are exact trimmed edges internally but pushed to CATIA as a polyline (0.05 mm chord).
* Performance is untested on a full silencer; per-sample distance queries are in Python.
  Check timing on your file, then we can optimise.
