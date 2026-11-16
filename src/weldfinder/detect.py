"""Edge-to-face weld candidate detection.

Everything is in millimetres. Geometry is never modified.

Algorithm (per ordered pair of solids A -> B whose bboxes, expanded by max_gap, overlap):
  1. Take the unique edges of A (shared edges counted once), dropping degenerate edges,
     seam edges, and edges between tangent-continuous faces (not physical terminations).
  2. Sample each edge by arc length; for each sample take the distance to the nearest
     B face (only faces whose bbox is near the edge are tested).
  3. Contiguous runs of samples with distance <= max_gap become candidates (rejected if the
     gap varies by more than max_gap_variation along the run); run ends are
     refined by bisection. The candidate curve is the original edge curve trimmed to the run.
  4. Candidates shorter than min_length are dropped; near-duplicates (same curve found from
     both sides) are merged keeping the smaller mean gap.

A candidate means "geometric proximity", NOT confirmed weld intent.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape, BRepExtrema_IsInFace
from OCP.Bnd import Bnd_Box
from OCP.GCPnts import GCPnts_AbscissaPoint, GCPnts_QuasiUniformDeflection
from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCP.GeomLProp import GeomLProp_SLProps
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp, TopExp_Explorer
try:  # class names differ between OCP releases
    from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_IndexedMapOfShape
except ImportError:
    from OCP.OCP.collections import (
        IndexedDataMap_TopoDS_Shape_List_TopoDS_Shape_TopTools_ShapeMapHasher as TopTools_IndexedDataMapOfShapeListOfShape,
        IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as TopTools_IndexedMapOfShape,
    )
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt

from ._compat import to_edge, to_face
from .step_io import Solid


@dataclass
class Params:
    max_gap: float = 5.0  # mm, max edge->face distance
    min_length: float = 3.0  # mm, drop shorter candidates (thin end-face edges etc.)
    step: float = 1.0  # mm, target sample spacing along edges
    tangent_deg: float = 5.0  # edges between faces meeting within this angle are skipped
    max_gap_variation: float = -1.0  # mm; reject runs whose gap varies more (edges running toward the face). <0: max_gap/2
    chord_tol: float = 0.05  # mm, polyline deflection for the exported curve
    dedup_tol: float = 1.0  # mm


@dataclass
class Candidate:
    id: str
    source: str  # solid id owning the edge
    target: str  # solid id owning the receiving face
    source_edge: int  # edge index within source solid (stable for a given file)
    curve_type: str
    length: float
    gap_min: float
    gap_mean: float
    gap_max: float
    face_fraction: float  # share of samples whose nearest target point is inside a face
    points: list[list[float]]  # polyline of the trimmed original curve
    notes: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return self.length * self.face_fraction

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["score"] = round(self.score, 3)
        return d


def _box(shape, enlarge=0.0) -> Bnd_Box:
    b = Bnd_Box()
    BRepBndLib.Add_s(shape, b)
    if enlarge:
        b.Enlarge(enlarge)
    return b


def _unique(shape, kind) -> list:
    m = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, kind, m)
    return [m.FindKey(i) for i in range(1, m.Extent() + 1)]


def _face_normal(face, p: gp_Pnt):
    surf = BRep_Tool.Surface_s(face)
    proj = GeomAPI_ProjectPointOnSurf(p, surf)
    if proj.NbPoints() == 0:
        return None
    u, v = proj.LowerDistanceParameters()
    props = GeomLProp_SLProps(surf, u, v, 1, 1e-6)
    if not props.IsNormalDefined():
        return None
    n = props.Normal()
    v = np.array([n.X(), n.Y(), n.Z()])
    return -v if face.Orientation() == TopAbs_REVERSED else v


def _physical_edges(solid: Solid, tangent_deg: float) -> list[tuple[int, object]]:
    """Unique edges that are plausible sheet terminations (index, edge)."""
    edge_faces = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.MapShapesAndAncestors_s(solid.shape, TopAbs_EDGE, TopAbs_FACE, edge_faces)
    cos_t = math.cos(math.radians(tangent_deg))
    out = []
    for i in range(1, edge_faces.Extent() + 1):
        edge = to_edge(edge_faces.FindKey(i))
        if BRep_Tool.Degenerated_s(edge):
            continue
        faces = [to_face(f) for f in edge_faces.FindFromIndex(i)]
        if any(BRep_Tool.IsClosed_s(edge, f) for f in faces):  # seam
            continue
        if len(faces) == 2:
            c = BRepAdaptor_Curve(edge)
            mid = c.Value(0.5 * (c.FirstParameter() + c.LastParameter()))
            n1, n2 = _face_normal(faces[0], mid), _face_normal(faces[1], mid)
            if n1 is not None and n2 is not None and float(n1 @ n2) > cos_t:
                continue  # smooth face boundary, not a physical edge
        out.append((i - 1, edge))
    return out


class _Dist:
    """Point -> nearest face distance among a fixed set of faces."""

    def __init__(self, faces):
        self.faces = faces
        self.ex = BRepExtrema_DistShapeShape()

    def __call__(self, p: gp_Pnt) -> tuple[float, bool]:
        v = BRepBuilderAPI_MakeVertex(p).Vertex()
        best, in_face = math.inf, False
        for f in self.faces:
            self.ex.LoadS1(v)
            self.ex.LoadS2(f)
            if not self.ex.Perform() or self.ex.NbSolution() == 0:
                continue
            d = self.ex.Value()
            if d < best:
                best = d
                in_face = self.ex.SupportTypeShape2(1) == BRepExtrema_IsInFace
        return best, in_face


def _polyline(curve: BRepAdaptor_Curve, u0: float, u1: float, tol: float) -> list[list[float]]:
    if curve.GetType().name == "GeomAbs_Line":
        pts = [curve.Value(u0), curve.Value(u1)]
    else:
        d = GCPnts_QuasiUniformDeflection(curve, tol, u0, u1)
        pts = [d.Value(i) for i in range(1, d.NbPoints() + 1)] if d.IsDone() else [
            curve.Value(u0 + (u1 - u0) * k / 32) for k in range(33)]
    return [[round(p.X(), 4), round(p.Y(), 4), round(p.Z(), 4)] for p in pts]


def _edge_candidates(a: Solid, b: Solid, edge_idx: int, edge, dist: _Dist, prm: Params) -> list[Candidate]:
    c = BRepAdaptor_Curve(edge)
    u0, u1 = c.FirstParameter(), c.LastParameter()
    length = GCPnts_AbscissaPoint.Length_s(c, u0, u1)
    if length < prm.min_length:
        return []
    n = max(8, min(400, math.ceil(length / prm.step)))
    us = [u0 + (u1 - u0) * k / n for k in range(n + 1)]
    ds = [dist(c.Value(u)) for u in us]
    ok = [d <= prm.max_gap for d, _ in ds]

    def refine(u_in: float, u_out: float) -> float:
        for _ in range(10):  # bisection on the threshold crossing
            um = 0.5 * (u_in + u_out)
            if dist(c.Value(um))[0] <= prm.max_gap:
                u_in = um
            else:
                u_out = um
        return u_in

    out = []
    k = 0
    while k <= n:
        if not ok[k]:
            k += 1
            continue
        s = k
        while k + 1 <= n and ok[k + 1]:
            k += 1
        e = k
        k += 1
        ua = refine(us[s], us[s - 1]) if s > 0 else us[s]
        ub = refine(us[e], us[e + 1]) if e < n else us[e]
        seg = ds[s:e + 1]
        gaps = np.array([d for d, _ in seg])
        var_tol = prm.max_gap_variation if prm.max_gap_variation >= 0 else prm.max_gap / 2
        if gaps.max() - gaps.min() > var_tol:
            continue  # edge heads toward/away from the face: not a seam running along it
        L = GCPnts_AbscissaPoint.Length_s(c, ua, ub)
        if L < prm.min_length:
            continue
        out.append(Candidate(
            id="", source=a.id, target=b.id, source_edge=edge_idx,
            curve_type=c.GetType().name.replace("GeomAbs_", ""),
            length=round(L, 3), gap_min=round(float(gaps.min()), 3),
            gap_mean=round(float(gaps.mean()), 3), gap_max=round(float(gaps.max()), 3),
            face_fraction=round(sum(f for _, f in seg) / len(seg), 3),
            points=_polyline(c, ua, ub, prm.chord_tol),
        ))
    return out


def _dedup(cands: list[Candidate], tol: float) -> list[Candidate]:
    """Merge the same physical curve found from both sides of a solid pair."""
    cands = sorted(cands, key=lambda c: c.gap_mean)
    kept: list[Candidate] = []
    for c in cands:
        P = np.array(c.points)
        dup = False
        for k in kept:
            if {k.source, k.target} != {c.source, c.target}:
                continue
            Q = np.array(k.points)
            probe = P[np.linspace(0, len(P) - 1, 5).astype(int)]
            if np.max(np.min(np.linalg.norm(probe[:, None] - Q[None], axis=2), axis=1)) < tol:
                dup = True
                break
        if not dup:
            kept.append(c)
    return kept


def detect(solids: list[Solid], prm: Params | None = None, sources: set[str] | None = None,
           targets: set[str] | None = None) -> list[Candidate]:
    """Candidates over `solids`. `sources`/`targets` (solid ids) restrict which solids own the
    edges / receive them; default: all solids both ways."""
    prm = prm or Params()
    boxes = {s.id: _box(s.shape, prm.max_gap) for s in solids}
    cands: list[Candidate] = []
    for a in solids:
        if sources is not None and a.id not in sources:
            continue
        edges = None
        for b in solids:
            if targets is not None and b.id not in targets:
                continue
            if a.id == b.id or boxes[a.id].IsOut(boxes[b.id]):
                continue
            if edges is None:
                edges = _physical_edges(a, prm.tangent_deg)
            b_faces = [(f, _box(f, prm.max_gap)) for f in _unique(b.shape, TopAbs_FACE)]
            for idx, edge in edges:
                eb = _box(edge)
                near = [f for f, fb in b_faces if not fb.IsOut(eb)]
                if near:
                    cands += _edge_candidates(a, b, idx, edge, _Dist(near), prm)
    cands = _dedup(cands, prm.dedup_tol)
    cands.sort(key=lambda c: -c.score)
    for i, c in enumerate(cands):
        c.id = f"C{i:04d}"
    return cands
