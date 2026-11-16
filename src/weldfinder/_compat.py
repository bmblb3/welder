"""Tiny shims so the code runs on both older (7.7) and newer (8.x) OCP releases."""
from OCP.TopoDS import TopoDS

to_edge = getattr(TopoDS, "Edge_s", None) or TopoDS.Edge
to_face = getattr(TopoDS, "Face_s", None) or TopoDS.Face
to_solid = getattr(TopoDS, "Solid_s", None) or TopoDS.Solid
