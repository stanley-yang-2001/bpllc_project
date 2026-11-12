@echo off
rem Runs, one after the other with nobody watching (version 2.3, 12 Nov 2026):
rem   1. the story test: cascade, 4 requests, reviewers gpt and qwen
rem   2. the refine test: baseline and refine on 10 English stories (key switching on)
rem   3. run-checks.bat --round
rem Also: keeps the computer awake, refuses to start while another run is going, and opens the Story Test Desk (live page) on http://localhost:8090.
rem SUMMARY.txt is updated when each step starts and ends. Needs keep-awake.ps1 in this folder. Add --shutdown to turn the computer off at the end. To cancel: shutdown /a
rem This file uses no if-blocks on purpose: one stray bracket in a block closed the window in version 2.
setlocal
set DOSHUTDOWN=0
if /i "%~1"=="--shutdown" set DOSHUTDOWN=1
cd /d "%~dp0"
mkdir test-reports 2>nul
if exist "test-reports\overnight.lock" goto locked

for /f %%i in ('powershell -nologo -command "Get-Date -Format yyyyMMdd_HHmmss"') do set STAMP=%%i
set OUT=test-reports\overnight-%STAMP%
mkdir "%OUT%" 2>nul
set SUMMARY=%OUT%\SUMMARY.txt
set FLAG=%OUT%\done.flag
echo %STAMP%> "test-reports\overnight.lock"
echo Overnight run started %DATE% %TIME% > "%SUMMARY%"
echo Started. Log folder: %OUT%

if not exist keep-awake.ps1 goto noawake
start "keep-awake" /min powershell -nologo -noprofile -executionpolicy bypass -file keep-awake.ps1 "%FLAG%"
echo Keeping the computer awake until this run ends. >> "%SUMMARY%"
goto awakedone
:noawake
echo WARNING: keep-awake.ps1 was not found next to this file. Windows may go to sleep and freeze the run. >> "%SUMMARY%"
echo WARNING: keep-awake.ps1 was not found next to this file.
:awakedone

if not exist scripts\story_desk.py goto nodesk
start "story-desk" /min python scripts\story_desk.py --no-browser
echo Story Test Desk: http://localhost:8090 >> "%SUMMARY%"
echo Story Test Desk is live at http://localhost:8090
goto deskdone
:nodesk
echo The Story Test Desk is not in this version of the project. >> "%SUMMARY%"
:deskdone

echo [0/3] Making sure the containers are up ...
docker compose up -d >> "%OUT%\00-docker-up.log" 2>&1
set UPCODE=%errorlevel%
echo docker compose up -d: exit code %UPCODE% >> "%SUMMARY%"
if not "%UPCODE%"=="0" goto dockerfail
goto story
:dockerfail
echo Docker did not start. Is Docker Desktop running? >> "%SUMMARY%"
goto finish

:story
echo Step 1 story test started %TIME% >> "%SUMMARY%"
echo [1/3] story test: cascade, 4 requests, reviewers gpt and qwen. Slow: it waits out Groq rate limits.
docker compose exec -T langflow python /app/scripts/run_story_methods.py --variants cascade --limit 4 --audit-models gpt,qwen --key-budget 90000 --out /app/scripts/overnight_%STAMP%.html > "%OUT%\01-story-test.log" 2>&1
set STORY=%errorlevel%
echo Step 1 story test: exit code %STORY% at %TIME%. 0 means it finished. >> "%SUMMARY%"
if not exist "scripts\overnight_%STAMP%.json" goto nostory
copy /y "scripts\overnight_%STAMP%.json" "%OUT%\" >nul
copy /y "scripts\overnight_%STAMP%.html" "%OUT%\" >nul 2>nul
echo     results copied into this folder: overnight_%STAMP%.json and .html. Send them to Claude. >> "%SUMMARY%"
goto refine
:nostory
echo     no results file was written. Read 01-story-test.log. A daily Groq limit stops the run: run it again with --resume. >> "%SUMMARY%"

:refine
echo Step 2 refine test started %TIME% >> "%SUMMARY%"
echo [2/3] refine test: baseline and refine, 10 English stories.
docker compose exec -T langflow python /app/scripts/run_story_methods.py --variants baseline,refine --languages en --count 10 --no-translate --audit-models gpt,qwen --key-budget 90000 --out /app/scripts/refine_%STAMP%.html > "%OUT%\02-refine-test.log" 2>&1
set REFINE=%errorlevel%
echo Step 2 refine test: exit code %REFINE% at %TIME%. 0 means it finished. >> "%SUMMARY%"
if not exist "scripts\refine_%STAMP%.json" goto norefine
copy /y "scripts\refine_%STAMP%.json" "%OUT%\" >nul
copy /y "scripts\refine_%STAMP%.html" "%OUT%\" >nul 2>nul
echo     results copied into this folder: refine_%STAMP%.json and .html. Send them to Claude. >> "%SUMMARY%"
goto checks
:norefine
echo     no results file was written. Read 02-refine-test.log. If a daily limit stopped it, run it again with --resume scripts\refine_%STAMP%.json. >> "%SUMMARY%"

:checks
echo Step 3 checks started %TIME% >> "%SUMMARY%"
echo [3/3] run-checks.bat --round. This takes a while.
cmd /c run-checks.bat --round > "%OUT%\03-checks.log" 2>&1
set CHECKS=%errorlevel%
echo Step 3 run-checks.bat --round: exit code %CHECKS% at %TIME%. 0 means every check passed. >> "%SUMMARY%"
echo     its own report is the newest folder in test-reports with REPORT.txt in it >> "%SUMMARY%"

:finish
echo Finished %DATE% %TIME% >> "%SUMMARY%"
del "test-reports\overnight.lock" 2>nul
echo done> "%FLAG%"
echo.
type "%SUMMARY%"
if not "%DOSHUTDOWN%"=="1" goto end
echo The computer shuts down in 2 minutes. To cancel: shutdown /a >> "%SUMMARY%"
shutdown /s /t 120 /c "run-overnight.bat finished. Run shutdown /a to cancel."
goto done
:end
echo.
echo Finished. The Story Test Desk keeps running in its own window until you close it. Press any key to close this window.
pause >nul
:done
endlocal
goto :eof

:locked
echo Another overnight run is already going: test-reports\overnight.lock exists.
echo Open http://localhost:8090 to watch it. If nothing is running, delete that file and start again.
pause
endlocal
