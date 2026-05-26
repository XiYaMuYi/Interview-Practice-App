@echo off
chcp 65001 >nul
cd /d D:\AI_Project\Surprise\Interview-Practice-App
echo [%date% %time%] Starting Claude Code... >> .claude-run.log
claude --permission-mode bypassPermissions --print "Read .claude-prompt.txt and follow the instructions. After completing the tasks, create a file named .claude-done.md" >> .claude-run.log 2>&1
echo [%date% %time%] Claude Code finished with exit code %ERRORLEVEL% >> .claude-run.log
