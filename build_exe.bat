@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtualenv...
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)

echo Installing runtime + build dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 exit /b 1

echo Building CatAutoclick.exe ...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean cat-autoclick.spec
if errorlevel 1 exit /b 1

echo.
echo Done: dist\CatAutoclick\CatAutoclick.exe
echo Presets will be saved next to the exe in a presets\ folder.
endlocal
