@echo off
chcp 65001 >nul 2>&1
title 转诊守门人AI智能体服务
echo ============================================
echo    转诊守门人AI智能体 - 启动中...
echo ============================================
echo.
cd /d "%~dp0"

echo 正在启动服务，请勿关闭本窗口...
echo 启动成功后，浏览器访问: http://localhost:8080/
echo.
rem 延迟5秒后再打开浏览器（等待服务就绪）
start /b cmd /c "timeout /t 5 /nobreak >nul & start \"\" http://localhost:8080/"

python main.py

echo.
echo 服务已停止。
pause