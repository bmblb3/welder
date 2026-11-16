# weldfinder

## FreeCAD buttons (current direction)
Interactive tools for preparing sheet-metal CAD for CFD, as a FreeCAD workbench ("WeldFinder").
Geometry work runs in the `weldfinder` engine (OCP/OCCT) inside FreeCAD's own Python.

**Install (once, on any OS):** open FreeCAD (1.x), View > Panels > Python console, then
    __file__ = r"C:\path\to\welder\freecad\install.py"; exec(open(__file__).read())
It pip-installs `cadquery-ocp==7.7.2` into FreeCAD's Python (7.7.x on purpose: newer wheels need
pip's VTK, which clashes with FreeCAD's) and copies the module to FreeCAD's user `Mod` folder.
Restart FreeCAD and choose the **WeldFinder** workbench.

**Button 1 - Find welds in selection:** select solid(s) in the tree/3D view, click it, enter the max
gap. 1 solid selected -> searched against all other visible solids; 2+ -> only between those.
Red curves appear in group `WeldCandidates` (label = ids, length, gap min/mean/max); re-running
replaces them; "Clear weld candidates" removes them. Curves are geometric proximity, not weld intent.

**Tests (no GUI):** `freecadcmd freecad/tests/test_flow.py` (prints `RESULT OK`), and `pytest` for the engine.

**Status:** engine + flow tested headless on Linux (FreeCAD 1.1.4). NOT yet tested: the toolbar GUI
(`InitGui.py`, no icons), Windows, a real silencer. FreeCAD's own `distToShape` costs ~5 ms/call, which
is why the engine is OCP rather than pure FreeCAD.

---
## CATIA bridge (earlier approach, kept for reference; superseded by FreeCAD)

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
  how the STEP document is named/located (`find_step_file` looks beside the part, then asks for the path; use `--step-file`; nothing is exported from CATIA).
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
