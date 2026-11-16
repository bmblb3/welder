"""WeldFinder logic for FreeCAD (no GUI imports, so it runs under freecadcmd).

Geometry work is done by the `weldfinder` engine (OCP/OCCT), because FreeCAD's own
Shape.distToShape costs ~5 ms per call. Shapes are handed over as BREP files.
Units: mm. Results are geometric proximity only, not confirmed weld intent.
"""
import os
import sys
import tempfile

import FreeCAD
import Part

_here = os.path.dirname(os.path.abspath(__file__))
for _p in (_here, os.path.join(_here, "..", "..", "src")):  # vendored copy, or repo checkout
    if os.path.isdir(os.path.join(_p, "weldfinder")) and _p not in sys.path:
        sys.path.insert(0, _p)

GROUP = "WeldCandidates"


def _engine():
    from weldfinder import detect as det  # imported lazily so errors show up as a message
    return det


def to_engine_solids(objs):
    """FreeCAD objects -> engine Solids (id = object Name, global placement baked in)."""
    from OCP.BRep import BRep_Builder
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS_Shape

    from weldfinder._compat import to_solid
    from weldfinder.step_io import Solid

    out = []
    tmp = tempfile.mkdtemp(prefix="weldfinder_")
    for o in objs:
        shp = getattr(o, "Shape", None)
        if shp is None or shp.isNull() or not shp.Solids:
            continue
        path = os.path.join(tmp, o.Name + ".brep")
        shp.exportBrep(path)
        s = TopoDS_Shape()
        if not BRepTools.Read_s(s, path, BRep_Builder()):
            continue
        exp, k = TopExp_Explorer(s, TopAbs_SOLID), 0
        found = []
        while exp.More():
            found.append(to_solid(exp.Current()))
            exp.Next()
        for k, sol in enumerate(found):
            out.append(Solid(o.Name if len(found) == 1 else f"{o.Name}#{k}", o.Label, sol))
        os.remove(path)
    os.rmdir(tmp)
    return out


def visible_solid_objects(doc):
    return [o for o in doc.Objects
            if hasattr(o, "Shape") and not o.Shape.isNull() and o.Shape.Solids
            and getattr(o, "Visibility", True)]


def make_curve(points):
    pts = [FreeCAD.Vector(*p) for p in points]
    if len(pts) == 2:
        return Part.makeLine(pts[0], pts[1])
    try:
        bs = Part.BSplineCurve()
        bs.interpolate(pts)
        return bs.toShape()
    except Exception:
        return Part.makePolygon(pts)


def find_welds(doc, selected, max_gap=5.0, min_length=3.0, limit=0):
    """Candidates for the selected solid objects. Returns (candidates, created_objects).

    2+ selected: only pairs among them. 1 selected: against all other visible solids.
    Previous results are replaced. limit>0 keeps only the best N.
    """
    det = _engine()
    sel = [o for o in selected if getattr(o, "Shape", None) is not None and o.Shape.Solids]
    if not sel:
        raise ValueError("Select at least one solid object first.")
    pool = sel if len(sel) >= 2 else sel + [o for o in visible_solid_objects(doc) if o not in sel]
    solids = to_engine_solids(pool)
    sel_ids = {s.id for s in solids if s.id.split("#")[0] in {o.Name for o in sel}}
    prm = det.Params(max_gap=max_gap, min_length=min_length)
    cands = det.detect(solids, prm, sources=sel_ids,
                       targets=sel_ids if len(sel) >= 2 else None)
    if limit > 0:
        cands = cands[:limit]
    label = {s.id: s.name for s in solids}

    clear_candidates(doc)
    grp = doc.addObject("App::DocumentObjectGroup", GROUP)
    made = []
    for c in cands:
        o = doc.addObject("Part::Feature", f"Weld_{c.id}")
        o.Shape = make_curve(c.points)
        o.Label = f"{c.id} {label[c.source]}->{label[c.target]} L={c.length:.1f} gap={c.gap_min:.2f}/{c.gap_mean:.2f}/{c.gap_max:.2f}"
        grp.addObject(o)
        if FreeCAD.GuiUp:
            vo = o.ViewObject
            vo.LineColor = (1.0, 0.0, 0.0)
            vo.PointColor = (1.0, 0.0, 0.0)
            vo.LineWidth = 4.0
        made.append(o)
    doc.recompute()
    return cands, made


def clear_candidates(doc):
    grp = doc.getObject(GROUP)
    if grp is None:
        return 0
    n = 0
    for o in list(grp.Group):
        doc.removeObject(o.Name)
        n += 1
    doc.removeObject(grp.Name)
    return n
