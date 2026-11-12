@echo off
rem Opens the Story Test Desk on this computer: live while a story test runs. Close this window to stop it.
cd /d "%~dp0"
python scripts\story_desk.py
pause
