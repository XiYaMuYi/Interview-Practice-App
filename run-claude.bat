@echo off
cd /d D:\AI_Project\Surprise\Interview-Practice-App
claude --permission-mode bypassPermissions --print "读取 .claude-task.md 并执行任务" > D:\AI_Project\Surprise\Interview-Practice-App\.claude-output.log 2>&1
if %ERRORLEVEL% EQU 0 (
    echo DONE > D:\AI_Project\Surprise\Interview-Practice-App\.claude-done.md
)
