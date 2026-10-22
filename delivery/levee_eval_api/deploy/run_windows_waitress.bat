@echo off
REM Windows deployment with waitress.  Run from the package root:  deploy\run_windows_waitress.bat
REM One-time setup:  py -3 -m venv .venv  &&  .venv\Scripts\pip install -r requirements-deploy.txt
chcp 65001 >nul
if "%LEVEE_EVAL_HOST%"=="" set LEVEE_EVAL_HOST=127.0.0.1
if "%LEVEE_EVAL_PORT%"=="" set LEVEE_EVAL_PORT=8080
if "%LEVEE_EVAL_THREADS%"=="" set LEVEE_EVAL_THREADS=8
.venv\Scripts\waitress-serve --listen=%LEVEE_EVAL_HOST%:%LEVEE_EVAL_PORT% --threads=%LEVEE_EVAL_THREADS% levee_eval.wsgi:application
