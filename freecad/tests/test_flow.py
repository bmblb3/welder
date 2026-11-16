"""Headless end-to-end test:  freecadcmd freecad/tests/test_flow.py   (prints RESULT OK/FAILED)"""
import math
import os
import sys
import traceback

import FreeCAD
import Part
from FreeCAD import Vector as V

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "WeldFinder"))
import weldtools  # noqa: E402


def scene():
    doc = FreeCAD.newDocument("t")
    for name, shp in (("Wall", Part.makeBox(100, 100, 2, V(-25, -25, -2))),
                      ("Plate", Part.makeBox(50, 1.5, 30, V(0, 0, 1.0))),
                      ("Far", Part.makeBox(5, 5, 5, V(500, 500, 500)))):
        doc.addObject("Part::Feature", name).Shape = shp
    return doc


def test_one_selected_vs_visible():
    doc = scene()
    c, made = weldtools.find_welds(doc, [doc.Plate])
    assert len(c) == 2 and len(made) == 2, [x.id for x in c]
    for o in made:
        assert abs(o.Shape.Length - 50) < 0.1
    assert doc.getObject("WeldCandidates") is not None and len(doc.WeldCandidates.Group) == 2


def test_two_selected_and_rerun_replaces():
    doc = scene()
    weldtools.find_welds(doc, [doc.Plate, doc.Wall])
    c, made = weldtools.find_welds(doc, [doc.Plate, doc.Wall], limit=1)
    assert len(c) == 1 and len(doc.WeldCandidates.Group) == 1
    assert weldtools.clear_candidates(doc) == 1 and doc.getObject("WeldCandidates") is None


def test_pair_excludes_unselected():
    doc = scene()
    assert weldtools.find_welds(doc, [doc.Plate, doc.Far])[0] == []


def test_curved_edge_is_spline():
    doc = FreeCAD.newDocument("t2")
    doc.addObject("Part::Feature", "Tube").Shape = Part.makeCylinder(51.5, 100).cut(Part.makeCylinder(50, 100))
    doc.addObject("Part::Feature", "Baffle").Shape = Part.makeCylinder(49, 1.5, V(0, 0, 50))
    c, made = weldtools.find_welds(doc, [doc.Baffle])
    assert len(made) == 2
    for o in made:
        assert abs(o.Shape.Length - 2 * math.pi * 49) < 0.5
        assert all(abs(math.hypot(p.x, p.y) - 49) < 0.1 for p in o.Shape.discretize(60))


failed = 0
for name, fn in list(globals().items()):
    if name.startswith("test_"):
        try:
            fn(); print("PASS", name)
        except Exception:
            failed += 1; print("FAIL", name); traceback.print_exc()
print("RESULT", "FAILED" if failed else "OK", failed)
