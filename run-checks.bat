@echo off
rem Runs every check the project has. Add --stack, --live, --all, --up, --list ... (see docs\TESTING.md).
cd /d "%~dp0"
python scripts\run_all_checks.py %*
exit /b %errorlevel%
