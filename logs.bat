@echo off
chcp 65001 >nul
echo Просмотр логов с правильной кодировкой UTF-8...
echo Для выхода нажмите Ctrl+C
echo.
docker compose logs -f bot
pause
