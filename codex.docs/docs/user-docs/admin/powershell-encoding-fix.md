# Решение проблемы с кодировкой UTF-8 в PowerShell

**Дата:** 14.10.2025 13:27

## Проблема

При работе с Git и PowerShell возникают проблемы с кодировкой:
- Коммиты с кириллицей создаются с кракозябрами
- Git log показывает кракозябры вместо русского текста
- Ошибки парсинга PowerShell скриптов

### Пример проблемы

```powershell
git commit -m "Тест: проверка кодировки"
# Результат: "РўРµСЃС‚: РїСЂРѕРІРµСЂРєР° РєРѕРґРёСЂРѕРІРєРё" (кракозябры)
```

## Причина

Проблема в версии PowerShell:

**Windows PowerShell 5.1 (Desktop):**
- Читает UTF-8 без BOM как ANSI (CP1251)
- Cursor/VS Code создает временные `ps-script-*.ps1` файлы в UTF-8 без BOM
- PowerShell 5.1 неправильно их читает → кракозябры

**PowerShell 7 (Core):**
- По умолчанию использует UTF-8
- Правильно читает UTF-8 без BOM
- Проблема отсутствует

## Решение

### Шаг 1: Установить PowerShell 7

```powershell
winget install --id Microsoft.PowerShell --source winget
```

### Шаг 2: Перезапустить терминал

Закройте и откройте терминал в Cursor/VS Code заново.

### Шаг 3: Проверить версию

```powershell
$PSVersionTable.PSEdition
# Должно быть: "Core"

$PSVersionTable.PSVersion
# Должно быть: 7.x.x
```

### Шаг 4: Протестировать

```powershell
echo "test" > test.txt
git add test.txt
git commit -m "Тест: проверка кодировки UTF-8"
git log -1 --pretty=format:"%s"
# Должно быть: "Тест: проверка кодировки UTF-8" (без кракозябр)
```

## Настройка PowerShell профиля

Если нужно, добавьте в профиль PowerShell (`$PROFILE`):

```powershell
# UTF-8 стек
try {
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [Console]::InputEncoding  = $utf8NoBom
    [Console]::OutputEncoding = $utf8NoBom
    $Global:OutputEncoding = $utf8NoBom
    if ($IsWindows) { chcp 65001 | Out-Null }
} catch {}

# Дефолты кодировок для cmdlet'ов
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$PSDefaultParameterValues['Set-Content:Encoding'] = 'utf8'
$PSDefaultParameterValues['Add-Content:Encoding'] = 'utf8'
```

## Настройка Git

Git должен быть настроен на UTF-8:

```powershell
git config --global i18n.commitencoding utf-8
git config --global i18n.logoutputencoding utf-8
git config --global core.quotepath false
git config --global core.autocrlf false
```

## Проверка

После установки PowerShell 7 проверьте:

```powershell
# 1. Версия PowerShell
$PSVersionTable.PSEdition  # Core
$PSVersionTable.PSVersion  # 7.x.x

# 2. Кодировка консоли
[Console]::OutputEncoding  # UTF-8

# 3. Git настройки
git config --global i18n.commitencoding  # utf-8
git config --global i18n.logoutputencoding  # utf-8

# 4. Тест коммита
echo "test" > test.txt
git add test.txt
git commit -m "Тест: проверка кодировки"
git log -1 --pretty=format:"%s"  # Должно быть без кракозябр
```

## Важно

- **Проблема не в Git** - Git настроен правильно
- **Проблема не в профиле PowerShell** - профиль настроен правильно
- **Проблема в версии PowerShell** - WinPS 5.1 не может правильно читать UTF-8 без BOM

## Альтернативное решение (если PowerShell 7 не подходит)

Если по каким-то причинам нельзя использовать PowerShell 7, используйте файл для коммитов:

```powershell
# Создать файл с сообщением коммита
"Ваше сообщение коммита" | Out-File -FilePath commit-msg.txt -Encoding UTF8

# Создать коммит
git commit -F commit-msg.txt

# Удалить временный файл
Remove-Item commit-msg.txt
```

Или используйте `git commit` без `-m` - откроется редактор.

## Резюме

- **Причина:** Windows PowerShell 5.1 читает UTF-8 без BOM как ANSI
- **Решение:** Установить PowerShell 7
- **Результат:** Все команды Git с кириллицей работают правильно

