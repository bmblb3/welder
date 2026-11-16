@echo off
rem Run on Windows. Usage: build_exe.bat [notest]   (notest skips the unit tests)
rem Use Python 3.12 (best PyInstaller/OCP wheel support).
py -3.12 -m venv .venv || exit /b 1
call .venv\Scripts\activate.bat
pip install -e .[exe,dev] || exit /b 1
if /i not "%1"=="notest" pytest -q || exit /b 1
pyinstaller --onefile --name weldfinder --collect-all OCP --hidden-import win32com.client ^
  --paths src weldfinder_exe.py || exit /b 1
echo Built dist\weldfinder.exe
