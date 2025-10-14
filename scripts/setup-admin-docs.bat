@echo off
REM Скрипт для автоматического развертывания админской документации
REM Запускается при первом развертывании сервера

echo 🚀 Начинаем развертывание админской документации...

REM Проверка существования папки
if not exist "docs\user-docs\admin" (
    echo Создаем папку для админской документации...
    mkdir docs\user-docs\admin
)

REM Проверка существования файлов
if not exist "docs\user-docs\admin\installation.md" (
    echo Создаем файл installation.md...
    copy /Y docs\installation.md docs\user-docs\admin\installation.md >nul 2>&1
)

if not exist "docs\user-docs\admin\quickstart.md" (
    echo Создаем файл quickstart.md...
    copy /Y codex-docs-admin-quickstart.md docs\user-docs\admin\quickstart.md >nul 2>&1
)

if not exist "docs\user-docs\admin\guide.md" (
    echo Создаем файл guide.md...
    copy /Y docs\admin-panel-guide.md docs\user-docs\admin\guide.md >nul 2>&1
)

if not exist "docs\user-docs\admin\security.md" (
    echo Создаем файл security.md...
    copy /Y docs\security-checklist.md docs\user-docs\admin\security.md >nul 2>&1
)

if not exist "docs\user-docs\admin\api.md" (
    echo Создаем файл api.md...
    copy /Y docs\api\README.md docs\user-docs\admin\api.md >nul 2>&1
)

REM Проверка _sidebar.md
findstr /C:"Админская документация" docs\user-docs\_sidebar.md >nul 2>&1
if errorlevel 1 (
    echo Обновляем _sidebar.md...
    echo. >> docs\user-docs\_sidebar.md
    echo --- >> docs\user-docs\_sidebar.md
    echo. >> docs\user-docs\_sidebar.md
    echo * **📖 Админская документация** >> docs\user-docs\_sidebar.md
    echo   * [⚡ Быстрый старт](admin/quickstart.md) >> docs\user-docs\_sidebar.md
    echo   * [📖 Полное руководство](admin/guide.md) >> docs\user-docs\_sidebar.md
    echo   * [🔒 Чек-лист безопасности](admin/security.md) >> docs\user-docs\_sidebar.md
    echo   * [🔌 API документация](admin/api.md) >> docs\user-docs\_sidebar.md
)

echo ✅ Админская документация успешно развернута!
echo 📖 Документация доступна по адресу: http://localhost:3001
echo.
echo Структура документации:
echo   📖 Админская документация
echo     ├── 🚀 Установка
echo     ├── ⚡ Быстрый старт
echo     ├── 📖 Полное руководство
echo     ├── 🔒 Чек-лист безопасности
echo     └── 🔌 API документация

