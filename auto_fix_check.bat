@echo off
cd /d "C:\Users\Lenov-2026\Documents\YT_VICTOR_PROJECTS\YT_Sports_Clipping_2026"
"C:\Users\Lenov-2026\AppData\Local\hermes\hermes-agent\venv\Scripts\auto-code-fixer" main.py --project-root . --no-ask --max-retries 2 >> auto_fix_log.txt 2>&1
echo --- Auto-fix check at %TIME% --- >> auto_fix_log.txt
