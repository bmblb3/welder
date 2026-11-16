import pytest
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir

from weldfinder.step_io import Solid


def box(x, y, z, dx, dy, dz):
    return BRepPrimAPI_MakeBox(gp_Pnt(x, y, z), dx, dy, dz).Shape()


def cyl(r, h, z0=0.0):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(0, 0, z0), gp_Dir(0, 0, 1)), r, h).Shape()


@pytest.fixture
def plate_on_wall():
    """Wall slab (top face z=0) and a 50x1.5x30 plate whose end sits 1.0 mm above it."""
    return [Solid("S000", "wall", box(-25, -25, -2, 100, 100, 2)),
            Solid("S001", "plate", box(0, 0, 1.0, 50, 1.5, 30))]


@pytest.fixture
def baffle_in_tube():
    """Tube (R_in 50, 1.5 thick) with a disc baffle R=49 -> 1.0 mm radial gap, curved edges."""
    tube = BRepAlgoAPI_Cut(cyl(51.5, 100), cyl(50, 100)).Shape()
    return [Solid("S000", "tube", tube), Solid("S001", "baffle", cyl(49, 1.5, 50))]


def write_step(solids, path):
    """Write solids as a flat named assembly to a STEP file (stand-in for a CATIA export)."""
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFApp import XCAFApp_Application
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)
    tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    for s in solids:
        lab = tool.AddShape(s.shape, False)
        TDataStd_Name.Set_s(lab, TCollection_ExtendedString(s.name))
    w = STEPCAFControl_Writer()
    w.Transfer(doc)
    w.Write(str(path))
