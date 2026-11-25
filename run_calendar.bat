@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 9))" >nul 2>nul
if errorlevel 1 goto use_python
py -3 launcher.py --desktop
set "APP_EXIT_CODE=%ERRORLEVEL%"
goto finished

:use_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python -c "import sys; raise SystemExit(sys.version_info < (3, 9))" >nul 2>nul
if errorlevel 1 goto no_python
python launcher.py --desktop
set "APP_EXIT_CODE=%ERRORLEVEL%"
goto finished

:no_python
echo Python 3.9 or newer was not found. Install Python 3.9+ and enable the py launcher or PATH entry.
pause
exit /b 1

:finished
echo.
echo 程序结束，按任意键关闭此窗口。
pause >nul
exit /b %APP_EXIT_CODE%
