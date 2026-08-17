@echo off
setlocal
set "CLAUDE_CONFIG_DIR="
if not defined REMEMBER_REAL_CLAUDE_BIN set "REMEMBER_REAL_CLAUDE_BIN=%USERPROFILE%\.local\bin\claude.exe"
"%REMEMBER_REAL_CLAUDE_BIN%" %*
exit /b %ERRORLEVEL%
