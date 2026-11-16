"""STEP import and solid enumeration (units: always millimetres)."""
from __future__ import annotations

from dataclasses import dataclass

from OCP.Interface import Interface_Static
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Shape

from ._compat import to_solid
from OCP.XCAFApp import XCAFApp_Application
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFDoc import XCAFDoc_DocumentTool

try:  # name differs between OCP releases
    from OCP.TDF import TDF_LabelSequence
except ImportError:
    from OCP.OCP.collections import Sequence_TDF_Label as TDF_LabelSequence


@dataclass
class Solid:
    id: str  # "S000", "S001", ... in traversal order; stable for a given file
    name: str  # product/body name from STEP ("" if none)
    shape: TopoDS_Shape


def _label_name(label: TDF_Label) -> str:
    attr = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return attr.Get().ToExtString()
    return ""


def load_solids(path: str) -> list[Solid]:
    """Read a STEP file and return every solid with its assembly location applied.

    Units are forced to mm (OCCT converts from whatever the file declares).
    """
    Interface_Static.SetCVal_s("xstep.cascade.unit", "MM")
    Interface_Static.SetIVal_s("read.stepcaf.subshapes.name", 1)

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)

    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    if reader.ReadFile(path) != IFSelect_RetDone:
        raise RuntimeError(f"Cannot read STEP file: {path}")
    if not reader.Transfer(doc):
        raise RuntimeError(f"STEP transfer failed: {path}")

    tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    tool.GetFreeShapes(roots)

    found: list[tuple[str, TopoDS_Shape]] = []

    def walk(label: TDF_Label, loc, name: str) -> None:
        if tool.IsAssembly_s(label):
            comps = TDF_LabelSequence()
            tool.GetComponents_s(label, comps)
            for i in range(1, comps.Length() + 1):
                comp = comps.Value(i)
                ref = TDF_Label()
                if tool.GetReferredShape_s(comp, ref):
                    walk(ref, loc * tool.GetLocation_s(comp), _label_name(ref) or name)
            return
        shape = tool.GetShape_s(label).Located(loc)
        exp = TopExp_Explorer(shape, TopAbs_SOLID)
        solids = []
        while exp.More():
            solids.append(to_solid(exp.Current()))
            exp.Next()
        for k, s in enumerate(solids):
            found.append((name if len(solids) == 1 else f"{name}#{k}", s))

    for i in range(1, roots.Length() + 1):
        root = roots.Value(i)
        walk(root, TopLoc_Location(), _label_name(root))

    return [Solid(f"S{i:03d}", n, s) for i, (n, s) in enumerate(found)]
