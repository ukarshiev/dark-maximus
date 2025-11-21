# Скрипт для проверки наличия результатов Allure перед генерацией отчета
# Используется для предотвращения генерации пустых отчетов

$ErrorActionPreference = "Stop"

Write-Host "=== Проверка наличия результатов Allure ===" -ForegroundColor Cyan
Write-Host ""

$hasResults = $false
$resultFiles = @()

if (Test-Path "allure-results") {
    # Проверяем наличие файлов результатов тестов
    $resultFiles = Get-ChildItem allure-results -Filter *-result.json -ErrorAction SilentlyContinue
    
    if ($resultFiles.Count -gt 0) {
        $hasResults = $true
        Write-Host "Найдено файлов результатов: $($resultFiles.Count)" -ForegroundColor Green
        Write-Host "Результаты готовы для генерации отчета" -ForegroundColor Green
    } else {
        Write-Host "ВНИМАНИЕ: Файлы результатов тестов не найдены!" -ForegroundColor Red
        Write-Host "Директория allure-results существует, но не содержит *-result.json файлов" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Возможные причины:" -ForegroundColor Yellow
        Write-Host "  1. Тесты не были запущены" -ForegroundColor Yellow
        Write-Host "  2. Тесты не сохраняют результаты в allure-results" -ForegroundColor Yellow
        Write-Host "  3. Неправильный путь к allure-results в pytest.ini" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Проверьте:" -ForegroundColor Yellow
        Write-Host "  - Запущены ли тесты: docker compose exec autotest pytest" -ForegroundColor Yellow
        Write-Host "  - Путь в pytest.ini: --alluredir=../allure-results (относительный от tests/)" -ForegroundColor Yellow
        Write-Host "  - conftest.py переопределяет путь на абсолютный от корня проекта" -ForegroundColor Yellow
        Write-Host "  - Volume-маппинг в docker-compose.yml: ./allure-results:/app/allure-results" -ForegroundColor Yellow
    }
    
    # Проверяем наличие executor.json
    if (Test-Path "allure-results\executor.json") {
        Write-Host "executor.json найден" -ForegroundColor Green
    } else {
        Write-Host "executor.json не найден (не критично)" -ForegroundColor Yellow
    }
    
    # Проверяем наличие history/
    if (Test-Path "allure-results\history") {
        Write-Host "history/ найдена" -ForegroundColor Green
    } else {
        Write-Host "history/ не найдена (не критично для первого запуска)" -ForegroundColor Yellow
    }
} else {
    Write-Host "ОШИБКА: Директория allure-results не существует!" -ForegroundColor Red
    Write-Host "Создайте директорию: mkdir allure-results" -ForegroundColor Yellow
}

Write-Host ""

if (-not $hasResults) {
    Write-Host "РЕЗУЛЬТАТ: Результаты тестов отсутствуют. Отчет не будет сгенерирован или будет пустым." -ForegroundColor Red
    exit 1
} else {
    Write-Host "РЕЗУЛЬТАТ: Результаты тестов найдены. Можно генерировать отчет." -ForegroundColor Green
    exit 0
}

