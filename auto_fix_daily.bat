@echo off
cd /d "C:\Users\Lenov-2026\Documents\YT_VICTOR_PROJECTS\YT_Sports_Clipping_2026"
"C:\Users\Lenov-2026\AppData\Local\hermes\hermes-agent\venv\Scripts\auto-code-fixer" main.py --project-root . --no-ask --max-retries 2 --timeout 120 >> auto_fix_log.txt 2>&1
echo [%TIME%] YT_Sports_Clipping_2026 auto-fix done >> auto_fix_log.txt
