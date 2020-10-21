@echo off

set MYDIR=%~dp0

where py >nul: 2>&1
if %ERRORLEVEL% NEQ 0 goto nopy

py -3 --version >nul: 2>&1
if %ERRORLEVEL% NEQ 0 goto nopy

set PY_LAUNCHER=py -3

goto :launch 

:nopy

where python >nul: 2>&1
if %ERRORLEVEL% NEQ 0 goto nopython

set PY_LAUNCHER=python

goto :launch 

:launch

%PY_LAUNCHER% %MYDIR%\wakeonlan %*

:nopython

>2 echo No Python found in path
exit /b 1