@echo off
chcp 65001 >nul 2>&1
title 转诊守门人 - 公网共享链接
echo ============================================
echo   转诊守门人AI智能体 - 公网链接一键启动
echo ============================================
cd /d "%~dp0"

echo [1/3] 清理可能残留的旧进程...
taskkill /F /IM ssh.exe >nul 2>&1

echo [2/3] 启动本地服务（8080端口）...
start "本地服务" /min cmd /c "cd /d %~dp0 && python main.py"
timeout /t 5 /nobreak >nul

echo [3/3] 启动SSH隧道，获取公网链接...
echo.
echo --------------------------------------------------
echo   链接生成后请立即复制保存！
echo   格式类似: https://xxxx.app.lhr.life
echo   窗口保持打开，链接才有效；关掉窗口链接即失效。
echo   （免费隧道地址每次启动都会变）
echo --------------------------------------------------
echo.
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:127.0.0.1:8080 nokey@localhost.run
echo.
echo 隧道已停止，链接已失效。
pause