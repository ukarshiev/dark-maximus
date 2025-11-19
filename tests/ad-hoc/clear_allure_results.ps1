# Скрипт для очистки старых результатов Allure перед новым запуском тестов
# Это гарантирует, что Allure покажет все тесты из текущего запуска, а не только уникальные testCaseId

$ErrorActionPreference = "Stop"

Write-Host "=== Очистка старых результатов Allure ===" -ForegroundColor Cyan
Write-Host ""

if (Test-Path "allure-results") {
    $fileCount = (Get-ChildItem allure-results -Filter *-result.json | Measure-Object).Count
    Write-Host "Найдено файлов результатов: $fileCount" -ForegroundColor Yellow
    
    Write-Host "Удаление старых результатов..." -ForegroundColor Yellow
    Remove-Item allure-results\*-result.json -Force -ErrorAction SilentlyContinue
    Remove-Item allure-results\*-container.json -Force -ErrorAction SilentlyContinue
    Remove-Item allure-results\*-attachment.* -Force -ErrorAction SilentlyContinue
    
    Write-Host "Старые результаты удалены" -ForegroundColor Green
} else {
    Write-Host "Директория allure-results не найдена, создаю..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path allure-results -Force | Out-Null
    Write-Host "Директория создана" -ForegroundColor Green
}

Write-Host ""
Write-Host "Теперь можно запускать тесты. Allure покажет все тесты из текущего запуска." -ForegroundColor Green

