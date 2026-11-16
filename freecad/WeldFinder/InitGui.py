import FreeCAD
import FreeCADGui


class _FindWelds:
    def GetResources(self):
        return {"MenuText": "Find welds in selection",
                "ToolTip": "Select one or more solids, then find candidate weld curves "
                           "(edge near another solid's face). 1 selected: vs all visible solids; "
                           "2+: only between the selected.",
                "Pixmap": ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        from PySide import QtGui
        import weldtools
        doc = FreeCAD.ActiveDocument
        sel = [o for o in FreeCADGui.Selection.getSelection()]
        try:
            gap, ok = QtGui.QInputDialog.getDouble(None, "WeldFinder", "Max gap (mm):", 5.0, 0.01, 1000.0, 2)
            if not ok:
                return
            cands, made = weldtools.find_welds(doc, sel, max_gap=gap)
        except Exception as e:  # show instead of failing silently
            QtGui.QMessageBox.warning(None, "WeldFinder", str(e))
            return
        FreeCAD.Console.PrintMessage(f"WeldFinder: {len(cands)} candidates\n")
        for c in cands:
            FreeCAD.Console.PrintMessage(f"  {c.id} {c.source}->{c.target} {c.curve_type} "
                                         f"L={c.length:.1f} gap {c.gap_min:.2f}/{c.gap_mean:.2f}/{c.gap_max:.2f}\n")
        if not cands:
            QtGui.QMessageBox.information(None, "WeldFinder", f"No candidates within {gap} mm.")


class _Clear:
    def GetResources(self):
        return {"MenuText": "Clear weld candidates", "ToolTip": "Remove the WeldCandidates group", "Pixmap": ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        import weldtools
        weldtools.clear_candidates(FreeCAD.ActiveDocument)
        FreeCAD.ActiveDocument.recompute()


class WeldFinderWorkbench(Workbench):
    MenuText = "WeldFinder"
    ToolTip = "Prepare sheet-metal CAD for CFD: weld candidates"

    def Initialize(self):
        FreeCADGui.addCommand("WeldFinder_FindWelds", _FindWelds())
        FreeCADGui.addCommand("WeldFinder_Clear", _Clear())
        cmds = ["WeldFinder_FindWelds", "WeldFinder_Clear"]
        self.appendToolbar("WeldFinder", cmds)
        self.appendMenu("WeldFinder", cmds)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(WeldFinderWorkbench())
