@echo off
chcp 65001 >nul
title AI 截面慣性矩網頁版
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set PYTHON_CMD=py -3
) else (
    set PYTHON_CMD=python
)

%PYTHON_CMD% -m pip install -U -r requirements.txt
%PYTHON_CMD% -m streamlit run streamlit_app.py
pause
