# Скрипт для запуска pylint с правильной кодировкой UTF-8 в Windows PowerShell
# Использование: .\scripts\lint.ps1

# Устанавливаем UTF-8 кодировку для консоли
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$OutputEncoding = [System.Text.Encoding]::UTF8

# Запускаем pylint с параметрами
python -m pylint src/shop_bot/ --disable=C0111,C0103 --fail-under=7.0

# Возвращаем код выхода
exit $LASTEXITCODE

