@echo off
cd /d "C:\Users\Lenov-2026\Documents\YT_VICTOR_PROJECTS\YT_Sports_Clipping_2026"
set PATH=C:\Users\Lenov-2026\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin;%PATH%
:LOOP
start /B "" "C:\Users\Lenov-2026\Documents\YT_VICTOR_PROJECTS\YT_Sports_Clipping_2026\venv\Scripts\pythonw.exe" "C:\Users\Lenov-2026\Documents\YT_VICTOR_PROJECTS\YT_Sports_Clipping_2026\main.py" --daemon
ping -n 30 127.0.0.1 > nul 2>&1
echo Daemon restarted at %TIME% >> bot.log
goto LOOP
