# Скрипт для анализа расхождения между терминалом и Allure
$ErrorActionPreference = "Stop"

Write-Host "=== Анализ расхождения между терминалом и Allure ===" -ForegroundColor Cyan
Write-Host ""

$allResults = Get-ChildItem allure-results -Filter *-result.json | Sort-Object LastWriteTime -Descending
Write-Host "Всего файлов результатов в allure-results: $($allResults.Count)" -ForegroundColor Yellow
Write-Host ""

$latestResults = $allResults | Select-Object -First 500
Write-Host "=== Статистика последних 500 результатов ===" -ForegroundColor Cyan

$stats = @{
    passed = 0
    failed = 0
    skipped = 0
    broken = 0
}

$uniqueTestCases = @{}

foreach ($file in $latestResults) {
    try {
        $content = Get-Content $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($content.status) {
            $stats[$content.status]++
            if ($content.testCaseId) {
                $uniqueTestCases[$content.testCaseId] = $true
            }
        }
    } catch {
        Write-Host "Ошибка при чтении файла $($file.Name)" -ForegroundColor Red
    }
}

Write-Host "Статистика по статусам:" -ForegroundColor Yellow
Write-Host "  passed: $($stats.passed)" -ForegroundColor White
Write-Host "  failed: $($stats.failed)" -ForegroundColor White
Write-Host "  skipped: $($stats.skipped)" -ForegroundColor White
Write-Host "  broken: $($stats.broken)" -ForegroundColor White

$total = $stats.passed + $stats.failed + $stats.skipped + $stats.broken
Write-Host "  Всего: $total" -ForegroundColor Green
Write-Host ""

Write-Host "=== Уникальные testCaseId ===" -ForegroundColor Cyan
Write-Host "Уникальных testCaseId в последних 500: $($uniqueTestCases.Count)" -ForegroundColor Yellow
Write-Host ""

Write-Host "=== Сравнение с данными из терминала ===" -ForegroundColor Cyan
Write-Host "Терминал: 403 passed, 43 failed, 3 skipped = 449 тестов" -ForegroundColor Yellow
Write-Host "Allure (последние 500): $($stats.passed) passed, $($stats.failed) failed, $($stats.skipped) skipped = $total тестов" -ForegroundColor Yellow
Write-Host ""

$diffPassed = 403 - $stats.passed
$diffFailed = 43 - $stats.failed
$diffSkipped = 3 - $stats.skipped

if ($diffPassed -ne 0 -or $diffFailed -ne 0 -or $diffSkipped -ne 0) {
    Write-Host "Расхождения:" -ForegroundColor Red
    if ($diffPassed -ne 0) {
        Write-Host "  passed: разница $diffPassed" -ForegroundColor Red
    }
    if ($diffFailed -ne 0) {
        Write-Host "  failed: разница $diffFailed" -ForegroundColor Red
    }
    if ($diffSkipped -ne 0) {
        Write-Host "  skipped: разница $diffSkipped" -ForegroundColor Red
    }
} else {
    Write-Host "Данные совпадают!" -ForegroundColor Green
}
Write-Host ""

$latestTime = ($latestResults | Select-Object -First 1).LastWriteTime
Write-Host "=== Время последнего обновления ===" -ForegroundColor Cyan
Write-Host "Последний файл результата: $latestTime" -ForegroundColor Yellow
Write-Host ""

Write-Host "=== Рекомендации ===" -ForegroundColor Cyan
Write-Host "1. Allure группирует тесты по testCaseId и показывает только последний результат" -ForegroundColor Yellow
Write-Host "2. Для отображения всех тестов нужно настроить Allure для показа всех запусков" -ForegroundColor Yellow
Write-Host "3. Warnings не записываются в Allure из-за --disable-warnings в pytest.ini" -ForegroundColor Yellow
Write-Host "4. Возможно, нужно очистить старые результаты или настроить KEEP_HISTORY_LATEST" -ForegroundColor Yellow
