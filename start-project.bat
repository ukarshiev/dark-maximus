@echo off
chcp 65001 >nul
echo ========================================
echo   dark-maximus v.1 - Запуск проекта
echo ========================================
echo.
echo Кодировка UTF-8 активирована
echo.
echo Доступные команды:
echo   docker compose up -d        - Запуск проекта
echo   docker compose down         - Остановка проекта  
echo   docker compose logs -f bot  - Просмотр логов
echo   docker compose restart bot  - Перезапуск бота
echo.
echo Для выхода введите: exit
echo ========================================
echo.

cmd /k
