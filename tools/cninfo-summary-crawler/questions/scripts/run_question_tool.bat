@echo off
chcp 65001 >nul
python -X utf8 "%~dp0question_set_tool.py" %*
if errorlevel 1 pause
