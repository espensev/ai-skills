@echo off
py -3 "%~dp0Invoke-RememberAdapter.py" %*
exit /b %ERRORLEVEL%
