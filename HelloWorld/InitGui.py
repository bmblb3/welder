import FreeCAD
import FreeCADGui


class HelloWorldCommand:
    def GetResources(self):
        return {"MenuText": "Hello World", "ToolTip": "Print 'Hello, World!'"}

    def Activated(self):
        FreeCAD.Console.PrintMessage("Hello, World!\n")

    def IsActive(self):
        return True


FreeCADGui.addCommand("HelloWorld_Say", HelloWorldCommand())


class HelloWorldWorkbench(FreeCADGui.Workbench):
    MenuText = "Hello World"
    ToolTip = "A minimal hello world workbench"

    def Initialize(self):
        self.appendToolbar("Hello World", ["HelloWorld_Say"])
        self.appendMenu("Hello World", ["HelloWorld_Say"])

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(HelloWorldWorkbench())
