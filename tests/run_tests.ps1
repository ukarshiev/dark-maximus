# Скрипт запуска тестов с генерацией Allure отчетов (PowerShell)
# Использование: .\run_tests.ps1 [опции pytest]

param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$PytestArgs
)

# Запуск pytest с параметрами Allure
$allureResults = Join-Path $PSScriptRoot "..\allure-results"
pytest --alluredir=$allureResults $PytestArgs

# Проверка успешности выполнения
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Тесты успешно выполнены. Результаты сохранены в allure-results/" -ForegroundColor Green
    Write-Host "📊 Для просмотра отчета запустите: allure serve allure-results" -ForegroundColor Cyan
} else {
    Write-Host "❌ Тесты завершились с ошибками. Проверьте allure-results/ для деталей." -ForegroundColor Red
    exit 1
}

