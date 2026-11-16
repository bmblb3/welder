import FreeCAD
import FreeCADGui


class WelderPanel:
    def __init__(self):
        from PySide import QtGui
        self.A, self.B = [], []  # lists of (objname, subname)
        self.form = QtGui.QWidget()
        self.form.setWindowTitle("Welder")
        lay = QtGui.QVBoxLayout(self.form)
        self.lbl = QtGui.QLabel()
        lay.addWidget(self.lbl)
        for text, fn in (("Set A from selection", lambda: self.setside("A")),
                         ("Set B from selection", lambda: self.setside("B")),
                         ("Show A only", lambda: self.show("A")),
                         ("Show B only", lambda: self.show("B")),
                         ("Show all", lambda: self.show("all")),
                         ("Seal", self.seal)):
            b = QtGui.QPushButton(text)
            b.clicked.connect(fn)
            lay.addWidget(b)
        self.out = QtGui.QPlainTextEdit()
        self.out.setReadOnly(True)
        lay.addWidget(self.out)
        self.refresh()

    def refresh(self):
        self.lbl.setText(f"A: {len(self.A)} faces   B: {len(self.B)} faces")

    def setside(self, side):
        items = []
        for sel in FreeCADGui.Selection.getSelectionEx():
            for sub in sel.SubElementNames:
                if sub.startswith("Face"):
                    items.append((sel.Object.Name, sub))
        setattr(self, side, items)
        self.refresh()

    def _owners(self, side):
        return {o for o, _ in (self.A if side == "A" else self.B)}

    def show(self, which):
        doc = FreeCAD.ActiveDocument
        keep = set()
        if which == "A":
            keep = self._owners("A")
        elif which == "B":
            keep = self._owners("B")
        for o in doc.Objects:
            if hasattr(o, "ViewObject") and o.ViewObject and hasattr(o, "Shape"):
                o.ViewObject.Visibility = (which == "all") or o.Name in keep

    def _faces(self, items):
        doc = FreeCAD.ActiveDocument
        return [doc.getObject(o).getSubObject(s, 1) for o, s in items]  # global placement

    def seal(self):
        import importlib
        import seal as S
        importlib.reload(S)
        if not self.A or not self.B:
            self.out.appendPlainText("Set both A and B first.")
            return
        try:
            shape, info = S.seal(self._faces(self.A), self._faces(self.B))
        except Exception as e:
            self.out.appendPlainText(f"FAILED: {e}")
            return
        doc = FreeCAD.ActiveDocument
        obj = doc.addObject("Part::Feature", "Seal")
        obj.Shape = shape
        doc.recompute()
        self.out.appendPlainText(f"OK gap={info['gap']:.4g} r={info['r']:.4g} vol={info['volume']:.4g}")

    def getStandardButtons(self):
        return 0x00200000  # Close


class WelderCommand:
    def GetResources(self):
        return {"MenuText": "Seal panel", "ToolTip": "Open the Welder A/B seal panel"}

    def Activated(self):
        FreeCADGui.Control.showDialog(WelderPanel())

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None


FreeCADGui.addCommand("Welder_Panel", WelderCommand())


class WelderWorkbench(FreeCADGui.Workbench):
    MenuText = "Welder"
    ToolTip = "Seal gaps between silencer bodies"

    def Initialize(self):
        self.appendToolbar("Welder", ["Welder_Panel"])
        self.appendMenu("Welder", ["Welder_Panel"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(WelderWorkbench())
