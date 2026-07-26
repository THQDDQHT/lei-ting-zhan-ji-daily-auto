@echo off
chcp 65001 >nul
cd /d "%~dp0"
python main.py --window-title "雷霆战机：集结" --capture-method printwindow --click-method message --sections interstellar,shop,team,stamina
pause
