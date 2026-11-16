"""CATIA V5 bridge (Windows COM via pywin32).

!! Written against the CATIA V5 Automation API from documentation; it could NOT be run
!! against a real CATIA in the development sandbox. Expect to adjust details on first use.
Only `match_visible` is covered by automated tests (with a fake CATIA).

Assumptions:
  * The STEP was opened in CATIA as a PartDocument whose solid bodies are in `Part.Bodies`.
  * Model coordinates in CATIA == STEP coordinates in mm (no assembly repositioning).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .step_io import Solid

STEP_EXTS = (".stp", ".step", ".p21")


@dataclass
class CatiaBody:
    name: str
    visible: bool


def _norm(n: str) -> str:
    return n.strip().lower()


def match_visible(solids: list[Solid], bodies: list[CatiaBody]) -> tuple[list[Solid], str]:
    """Pick the STEP solids that correspond to visible CATIA bodies.

    Returns (solids, how), `how` being "name", "order" or "none". Match by unique name first
    (STEP names like "Part2#0" are tried with the "#k" suffix stripped too), then by order if the
    counts agree. If neither works the match is "none" and ALL solids are returned: the caller
    must warn that visibility was NOT applied.
    """
    def strip(n: str) -> str:
        return _norm(n.split("#")[0])

    for key in (_norm, strip):
        names = [_norm(b.name) for b in bodies]
        snames = [key(s.name) for s in solids]
        if len(set(names)) == len(names) and len(set(snames)) == len(snames) and set(names) <= set(snames):
            vis = {n for n, b in zip(names, bodies) if b.visible}
            return [s for s, n in zip(solids, snames) if n in vis], "name"
    if len(bodies) == len(solids):
        return [s for s, b in zip(solids, bodies) if b.visible], "order"
    return list(solids), "none"


# ---------------------------------------------------------------- COM access

def connect():
    import win32com.client  # pywin32; Windows only

    try:
        return win32com.client.GetActiveObject("CATIA.Application")
    except Exception as e:  # com_error
        raise RuntimeError("CATIA is not running (could not attach to CATIA.Application)") from e


def _get_show(sel) -> bool:
    vp = sel.VisProperties
    try:
        r = vp.GetShow()
    except TypeError:
        r = vp.GetShow(0)
    if isinstance(r, tuple):
        r = r[-1] if len(r) > 1 else r[0]
    return int(r) == 0  # catVisPropertyShowAttr = 0, catVisPropertyNoShowAttr = 1


def read_bodies(doc) -> list[CatiaBody]:
    sel = doc.Selection
    out = []
    bodies = doc.Part.Bodies
    for i in range(1, bodies.Count + 1):
        b = bodies.Item(i)
        try:
            if b.Shapes.Count == 0:  # empty body (e.g. unused PartBody) has no STEP solid
                continue
        except Exception:
            pass
        sel.Clear()
        sel.Add(b)
        out.append(CatiaBody(b.Name, _get_show(sel)))
    sel.Clear()
    return out


def find_step_file(doc) -> str:
    """Locate the STEP file on disk; never exports from CATIA.

    Tries the document's own path, a same-named .stp/.step beside it, then the only STEP file in
    that folder. Raises FileNotFoundError if none is found (caller asks for the path).
    """
    full = str(doc.FullName)
    if full.lower().endswith(STEP_EXTS) and os.path.isfile(full):
        return full
    stem = os.path.splitext(os.path.basename(full))[0]
    folder = str(getattr(doc, "Path", "") or "")
    if folder and os.path.isdir(folder):
        for ext in STEP_EXTS:
            cand = os.path.join(folder, stem + ext)
            if os.path.isfile(cand):
                return cand
        steps = [f for f in os.listdir(folder) if f.lower().endswith(STEP_EXTS)]
        if len(steps) == 1:
            return os.path.join(folder, steps[0])
    raise FileNotFoundError(f"no STEP file found for {full}")


def push_curve(doc, points: list[list[float]], name: str) -> str:
    """Create a polyline (or line) through `points` in a new geometrical set. Returns its name."""
    part = doc.Part
    hsf = part.HybridShapeFactory
    gs = part.HybridBodies.Add()
    gs.Name = name
    pts_set = gs.HybridBodies.Add()
    pts_set.Name = "points"

    refs = []
    for x, y, z in points:
        p = hsf.AddNewPointCoord(x, y, z)
        pts_set.AppendHybridShape(p)
        refs.append(part.CreateReferenceFromObject(p))

    if len(refs) == 2:
        curve = hsf.AddNewLinePtPt(refs[0], refs[1])
    else:
        try:
            curve = hsf.AddNewPolyline()
            for i, r in enumerate(refs, 1):
                curve.InsertElement(r, i)
        except Exception:  # older V5 releases: join individual segments instead
            segs = []
            for a, b in zip(refs, refs[1:]):
                s = hsf.AddNewLinePtPt(a, b)
                gs.AppendHybridShape(s)
                segs.append(part.CreateReferenceFromObject(s))
            curve = hsf.AddNewJoin(segs[0], segs[1])
            for s in segs[2:]:
                curve.AddElement(s)
    curve.Name = name + "_curve"
    gs.AppendHybridShape(curve)

    sel = doc.Selection  # hide the helper points so only the curve shows
    sel.Clear()
    sel.Add(pts_set)
    sel.VisProperties.SetShow(1)
    sel.Clear()

    part.InWorkObject = curve
    part.Update()
    return name
