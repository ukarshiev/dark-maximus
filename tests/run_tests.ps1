#!/usr/bin/env pwsh
# Скрипт для запуска всех тестов с сохранением результатов в Allure
#
# Использование:
#   .\tests\run_tests.ps1                    # Запустить все тесты
#   .\tests\run_tests.ps1 -TestPath "tests/unit"  # Запустить только unit-тесты
#   .\tests\run_tests.ps1 -Verbose          # Подробный вывод

param(
    [string]$TestPath = "",
    [switch]$Verbose,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

Write-Host "🧪 Запуск тестов Dark Maximus" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Очистка allure-results если указан флаг --clean
if ($Clean) {
    Write-Host "🧹 Очистка allure-results..." -ForegroundColor Yellow
    docker compose exec autotest sh -c "rm -f /app/allure-results/*.json /app/allure-results/*.txt 2>/dev/null || true"
    Write-Host "✅ Очистка завершена" -ForegroundColor Green
}

# Формирование команды pytest
$pytestCmd = "pytest"
if ($TestPath) {
    $pytestCmd += " $TestPath"
}
if ($Verbose) {
    $pytestCmd += " -v"
} else {
    $pytestCmd += " -q"
}
$pytestCmd += " --tb=short"

Write-Host "📝 Команда: $pytestCmd" -ForegroundColor Gray
Write-Host ""

# Запуск тестов БЕЗ флага -T для корректного сохранения результатов Allure
Write-Host "⏳ Выполнение тестов..." -ForegroundColor Yellow
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "logs/pytest_$timestamp.log"

try {
    # Запуск тестов с сохранением в лог
    # КРИТИЧЕСКИ ВАЖНО: используем -w /app для корректного сохранения результатов
    docker compose exec -w /app autotest $pytestCmd 2>&1 | Tee-Object -FilePath $logFile
    $exitCode = $LASTEXITCODE
    
    Write-Host ""
    if ($exitCode -eq 0) {
        Write-Host "✅ Все тесты прошли успешно!" -ForegroundColor Green
    } elseif ($exitCode -eq 1) {
        Write-Host "⚠️  Некоторые тесты провалились" -ForegroundColor Yellow
    } else {
        Write-Host "❌ Ошибка выполнения тестов (exit code: $exitCode)" -ForegroundColor Red
    }
    
    # Проверка результатов Allure
    Write-Host ""
    Write-Host "📊 Проверка результатов Allure..." -ForegroundColor Cyan
    $resultCount = docker compose exec autotest sh -c "find /app/allure-results -name '*-result.json' -type f | wc -l"
    Write-Host "📁 Сохранено результатов: $resultCount" -ForegroundColor Gray
    
    if ($resultCount -gt 0) {
        Write-Host "✅ Результаты сохранены в allure-results/" -ForegroundColor Green
        Write-Host "🌐 Отчет будет доступен через ~30 секунд на:" -ForegroundColor Cyan
        Write-Host "   http://localhost:50005/allure-docker-service/projects/default/reports/latest/index.html" -ForegroundColor Blue
    } else {
        Write-Host "⚠️  Результаты не сохранены! Проверьте конфигурацию Allure" -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "📄 Лог сохранен: $logFile" -ForegroundColor Gray
    
    exit $exitCode
} catch {
    Write-Host "❌ Ошибка: $_" -ForegroundColor Red
    exit 1
}
