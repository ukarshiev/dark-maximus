# ============================================================================
# Setup Test Environment - Python UTF-8 Configuration
# ============================================================================
# Автоматическая настройка окружения для корректной работы Python тестов
# с Unicode-символами (эмодзи) в Windows PowerShell
# ============================================================================

param(
    [switch]$Global,  # Установить переменные глобально в системные переменные окружения
    [switch]$Test,    # Запустить тесты после настройки
    [switch]$Help     # Показать справку
)

if ($Help) {
    Write-Host "Setup Test Environment - Python UTF-8 Configuration" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Использование:" -ForegroundColor Yellow
    Write-Host "  .\setup_test_environment.ps1           # Настройка для текущей сессии"
    Write-Host "  .\setup_test_environment.ps1 -Global   # Глобальная настройка системы"
    Write-Host "  .\setup_test_environment.ps1 -Test     # Настройка + запуск тестов"
    Write-Host "  .\setup_test_environment.ps1 -Help     # Показать эту справку"
    Write-Host ""
    Write-Host "Параметры:" -ForegroundColor Yellow
    Write-Host "  -Global    Установить переменные окружения глобально в системе"
    Write-Host "  -Test      Запустить тесты после настройки"
    Write-Host "  -Help      Показать справку"
    exit 0
}

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "НАСТРОЙКА ОКРУЖЕНИЯ ДЛЯ PYTHON ТЕСТОВ" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

# ----------------------------------------------------------------------------
# 1. ПРОВЕРКА ТЕКУЩЕГО СОСТОЯНИЯ
# ----------------------------------------------------------------------------
Write-Host "1. Проверка текущего состояния Python..." -ForegroundColor Yellow

try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✓ Python найден: $pythonVersion" -ForegroundColor Green
    } else {
        Write-Host "   ✗ Python не найден или не работает" -ForegroundColor Red
        Write-Host "   Установите Python и добавьте его в PATH" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   ✗ Ошибка при проверке Python: $_" -ForegroundColor Red
    exit 1
}

# Проверяем текущие настройки кодировки
Write-Host ""
Write-Host "2. Проверка текущих настроек кодировки..." -ForegroundColor Yellow

$currentSettings = python -c @"
import sys
print(f'Default encoding: {sys.getdefaultencoding()}')
print(f'stdout encoding: {sys.stdout.encoding}')
print(f'stderr encoding: {sys.stderr.encoding}')
print(f'PYTHONIOENCODING: {sys.getenv("PYTHONIOENCODING", "не установлен")}')
print(f'PYTHONUTF8: {sys.getenv("PYTHONUTF8", "не установлен")}')
"@ 2>&1

Write-Host "   Текущие настройки:" -ForegroundColor Gray
$currentSettings | ForEach-Object { Write-Host "     $_" -ForegroundColor Gray }

# ----------------------------------------------------------------------------
# 2. НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "3. Настройка переменных окружения..." -ForegroundColor Yellow

# Переменные для настройки
$envVars = @{
    'PYTHONIOENCODING' = 'utf-8'
    'PYTHONUTF8' = '1'
    'LESSCHARSET' = 'utf-8'
}

foreach ($var in $envVars.GetEnumerator()) {
    try {
        # Устанавливаем для текущей сессии
        Set-Item -Path "env:$($var.Key)" -Value $var.Value -Force
        Write-Host "   ✓ $($var.Key) = $($var.Value)" -ForegroundColor Green
        
        # Если запрошена глобальная настройка
        if ($Global) {
            try {
                [Environment]::SetEnvironmentVariable($var.Key, $var.Value, [EnvironmentVariableTarget]::User)
                Write-Host "     ✓ Глобально установлено для пользователя" -ForegroundColor Green
            } catch {
                Write-Warning "     ✗ Не удалось установить глобально: $_"
            }
        }
    } catch {
        Write-Warning "   ✗ Ошибка установки $($var.Key): $_"
    }
}

# ----------------------------------------------------------------------------
# 3. НАСТРОЙКА КОНСОЛИ
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "4. Настройка консоли..." -ForegroundColor Yellow

try {
    # Устанавливаем UTF-8 для консоли
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    chcp 65001 | Out-Null
    
    Write-Host "   ✓ Кодировка консоли: UTF-8" -ForegroundColor Green
} catch {
    Write-Warning "   ✗ Ошибка настройки консоли: $_"
}

# ----------------------------------------------------------------------------
# 5. ПРОВЕРКА НАСТРОЕК
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "5. Проверка настроек..." -ForegroundColor Yellow

$newSettings = python -c @"
import sys
print(f'Default encoding: {sys.getdefaultencoding()}')
print(f'stdout encoding: {sys.stdout.encoding}')
print(f'stderr encoding: {sys.stderr.encoding}')
print(f'PYTHONIOENCODING: {sys.getenv("PYTHONIOENCODING", "не установлен")}')
print(f'PYTHONUTF8: {sys.getenv("PYTHONUTF8", "не установлен")}')
"@ 2>&1

Write-Host "   Новые настройки:" -ForegroundColor Gray
$newSettings | ForEach-Object { Write-Host "     $_" -ForegroundColor Gray }

# Проверяем, что настройки применились
$utf8Configured = $newSettings -match "utf-8|UTF-8"
if ($utf8Configured.Count -ge 3) {
    Write-Host "   ✓ Настройки UTF-8 применены успешно" -ForegroundColor Green
} else {
    Write-Host "   ⚠ Некоторые настройки могут не примениться до перезапуска PowerShell" -ForegroundColor Yellow
}

# ----------------------------------------------------------------------------
# 6. ТЕСТИРОВАНИЕ UNICODE ВЫВОДА
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "6. Тестирование Unicode вывода..." -ForegroundColor Yellow

try {
    $testResult = python -c @"
try:
    print('✅ Тест эмодзи: Привет, мир! 🚀')
    print('✅ Русский текст: Тестирование кодировки')
    print('✅ Смешанный текст: Hello 世界! 🌍')
    print('SUCCESS: Все символы отображаются корректно')
except UnicodeEncodeError as e:
    print(f'ERROR: Ошибка кодировки: {e}')
    print('FAILED: Проблема с кодировкой не решена')
"@ 2>&1

    Write-Host "   Результат теста:" -ForegroundColor Gray
    $testResult | ForEach-Object { Write-Host "     $_" -ForegroundColor Gray }
    
    if ($testResult -match "SUCCESS") {
        Write-Host "   ✓ Unicode тест пройден успешно" -ForegroundColor Green
    } else {
        Write-Host "   ✗ Unicode тест не пройден" -ForegroundColor Red
    }
} catch {
    Write-Warning "   ✗ Ошибка при тестировании Unicode: $_"
}

# ----------------------------------------------------------------------------
# 7. ЗАПУСК ТЕСТОВ (если запрошено)
# ----------------------------------------------------------------------------
if ($Test) {
    Write-Host ""
    Write-Host "7. Запуск тестов..." -ForegroundColor Yellow
    
    $testFiles = @(
        "test_deeplink_comma_format.py",
        "test_deeplink_base64.py", 
        "test_deeplink_integration.py",
        "test_deeplink_functionality.py",
        "test_deeplink_new_user.py",
        "test_group_edit_fix.py"
    )
    
    foreach ($testFile in $testFiles) {
        $testPath = Join-Path $PSScriptRoot $testFile
        if (Test-Path $testPath) {
            Write-Host "   Запуск $testFile..." -ForegroundColor Gray
            try {
                python $testPath
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "     ✓ $testFile - успешно" -ForegroundColor Green
                } else {
                    Write-Host "     ✗ $testFile - ошибки" -ForegroundColor Red
                }
            } catch {
                Write-Host "     ✗ $testFile - исключение: $_" -ForegroundColor Red
            }
        } else {
            Write-Host "     ⚠ $testFile - файл не найден" -ForegroundColor Yellow
        }
    }
}

# ----------------------------------------------------------------------------
# 8. ИНСТРУКЦИИ
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "ИНСТРУКЦИИ" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

if ($Global) {
    Write-Host "✓ Переменные окружения установлены глобально" -ForegroundColor Green
    Write-Host "  Перезапустите PowerShell для применения изменений" -ForegroundColor Yellow
} else {
    Write-Host "✓ Переменные окружения установлены для текущей сессии" -ForegroundColor Green
    Write-Host "  Для постоянной настройки запустите: .\setup_test_environment.ps1 -Global" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Для проверки настроек используйте:" -ForegroundColor Cyan
Write-Host "  python tests/test_encoding.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Для запуска всех тестов используйте:" -ForegroundColor Cyan
Write-Host "  .\setup_test_environment.ps1 -Test" -ForegroundColor Gray
Write-Host ""

if ($Test) {
    Write-Host "✓ Настройка и тестирование завершены!" -ForegroundColor Green
} else {
    Write-Host "✓ Настройка завершена!" -ForegroundColor Green
}
