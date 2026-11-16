"""Install WeldFinder into FreeCAD. Run it INSIDE FreeCAD:

  GUI:      View > Panels > Python console, then
            __file__ = r"C:\path\to\welder\freecad\install.py"; exec(open(__file__).read())
  headless: freecadcmd install.py

It (1) pip-installs the geometry engine (cadquery-ocp 7.7.2, no deps) into FreeCAD's own Python,
(2) copies the WeldFinder module + engine into FreeCAD's user Mod folder. Restart FreeCAD after.
"""
import importlib.util
import os
import shutil
import subprocess
import sys

import FreeCAD

OCP_VERSION = "7.7.2"  # newer wheels need pip's VTK, which clashes with FreeCAD's bundled VTK


def _repo_root():
    here = globals().get("__file__")
    if here:
        return os.path.dirname(os.path.dirname(os.path.abspath(here)))
    raise RuntimeError("Run via exec(open(<path>).read()) with __file__ set (see docstring).")


def _freecad_python():
    exe = "python.exe" if os.name == "nt" else "python"
    cand = os.path.join(FreeCAD.getHomePath(), "bin", exe)
    if os.path.isfile(cand):
        return cand
    return sys.executable  # last resort (works when FreeCAD embeds a normal interpreter)


def _pip(py, *args):
    subprocess.check_call([py, "-m", "pip", *args])


def main(repo=None):
    repo = repo or _repo_root()
    py = _freecad_python()
    print(f"FreeCAD python: {py}")

    if importlib.util.find_spec("numpy") is None:
        _pip(py, "install", "numpy")
    try:
        _pip(py, "install", "--no-deps", f"cadquery-ocp=={OCP_VERSION}")
    except subprocess.CalledProcessError:
        print("pip failed. If you are offline/behind a proxy, install cadquery-ocp "
              f"=={OCP_VERSION} manually into FreeCAD's Python.")
        raise

    dest = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WeldFinder")
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(os.path.join(repo, "freecad", "WeldFinder"), dest, ignore=ignore)
    shutil.copytree(os.path.join(repo, "src", "weldfinder"), os.path.join(dest, "weldfinder"), ignore=ignore)
    print(f"Installed to {dest}\nRestart FreeCAD and pick the 'WeldFinder' workbench.")


main()
