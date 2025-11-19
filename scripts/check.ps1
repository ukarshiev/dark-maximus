# Скрипт для запуска всех линтеров (аналог make check)
# Использование: .\scripts\check.ps1

# Устанавливаем UTF-8 кодировку для консоли
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$env:PYTHONIOENCODING = "utf-8"
$env:LANG = "ru_RU.UTF-8"

Write-Host "Proverka koda..." -ForegroundColor Green
Write-Host ""

# Python linting (pylint)
Write-Host "=== Python linting (pylint) ===" -ForegroundColor Green
python -m pylint src/shop_bot/ --disable=C0111,C0103 --fail-under=7.0 2>&1
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 30) {
    Write-Host "Pylint finished with error: $LASTEXITCODE" -ForegroundColor Yellow
}

Write-Host ""

# Python formatting (black)
Write-Host "=== Python formatting (black) ===" -ForegroundColor Green
python -m black --check src/shop_bot/ 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Black found files that need formatting" -ForegroundColor Yellow
}

Write-Host ""

# Jinja2 templates (djlint)
Write-Host "=== Jinja2 templates (djlint) ===" -ForegroundColor Green
python -m djlint --check src/shop_bot/webhook_server/templates/ apps/user-cabinet/templates/ 2>&1 | Select-Object -First 50
if ($LASTEXITCODE -ne 0) {
    Write-Host "Djlint found issues in templates" -ForegroundColor Yellow
}

Write-Host ""

# JavaScript (eslint)
Write-Host "=== JavaScript (eslint) ===" -ForegroundColor Green
npx eslint apps/user-cabinet/static/js/ src/shop_bot/webhook_server/static/js/ apps/web-interface/server.js 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ESLint found issues in JavaScript files" -ForegroundColor Yellow
}

Write-Host ""

# HTML (htmlhint)
Write-Host "=== HTML (htmlhint) ===" -ForegroundColor Green
npx htmlhint apps/web-interface/src/*.html 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "HTMLHint found issues in HTML files" -ForegroundColor Yellow
}

Write-Host ""

# CSS (stylelint)
Write-Host "=== CSS (stylelint) ===" -ForegroundColor Green
npx stylelint "src/shop_bot/webhook_server/static/css/*.css" "apps/user-cabinet/static/css/*.css" --ignore-path .stylelintignore 2>&1 | Select-Object -First 30
if ($LASTEXITCODE -ne 0) {
    Write-Host "Stylelint found issues in CSS files" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[OK] Check completed" -ForegroundColor Green

