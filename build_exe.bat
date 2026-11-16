@echo off
rem Run on Windows. Use Python 3.12 (best PyInstaller/OCP wheel support).
py -3.12 -m venv .venv || exit /b 1
call .venv\Scripts\activate.bat
pip install -e .[exe,dev] || exit /b 1
pytest -q || exit /b 1
pyinstaller --onefile --name weldfinder --collect-all OCP --hidden-import win32com.client ^
  src\weldfinder\cli.py || exit /b 1
echo Built dist\weldfinder.exe
