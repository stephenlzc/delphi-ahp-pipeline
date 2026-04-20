@echo off
REM Delphi-AHP Pipeline Runner (Windows)
REM Double-click this file to run
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python app.py
