import FreeCAD
import FreeCADGui
import weldfinder_commands


class WeldFinderWorkbench(Workbench):
    MenuText = "WeldFinder"
    ToolTip = "Prepare sheet-metal CAD for CFD: weld candidates"
    Icon = weldfinder_commands.icon("FindWelds.svg")

    def Initialize(self):
        import weldfinder_commands  # must be imported here: InitGui globals are not visible

        cmds = weldfinder_commands.register()
        self.appendToolbar("WeldFinder", cmds)
        self.appendMenu("WeldFinder", cmds)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(WeldFinderWorkbench())
FreeCAD.Console.PrintMessage("WeldFinder workbench loaded\n")
