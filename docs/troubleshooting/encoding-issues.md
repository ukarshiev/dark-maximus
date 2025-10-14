# Решение проблем с кодировкой в Git и PowerShell

**Дата последней редакции:** 14.10.2025

## Проблема

При работе с Git в PowerShell на Windows могут возникать проблемы с отображением русских символов в коммитах. Коммиты отображаются с искаженной кодировкой (например, `РћР±РЅРѕРІР»РµРЅ` вместо `Обновлен`).

## Причина

Проблема возникает из-за несоответствия кодировок:
- Git по умолчанию может использовать Windows-1251 (CP1251)
- PowerShell по умолчанию использует кодировку консоли Windows
- GitHub и большинство современных инструментов ожидают UTF-8

## Решение

### 1. Глобальная настройка Git (уже выполнено)

Настройки Git уже применены глобально:

```powershell
git config --global core.quotepath false
git config --global i18n.commitencoding utf-8
git config --global i18n.logoutputencoding utf-8
git config --global gui.encoding utf-8
```

### 2. Настройка PowerShell профиля (уже выполнено)

В профиль PowerShell добавлены настройки для автоматической установки UTF-8 при каждом запуске терминала.

Проверить профиль можно командой:
```powershell
Get-Content $PROFILE
```

### 3. Ручная настройка для текущей сессии

Если нужно настроить кодировку вручную для текущей сессии:

```powershell
# Настройка PowerShell на UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
chcp 65001

# Настройка переменных окружения
$env:LESSCHARSET = 'utf-8'
```

### 4. Использование скрипта настройки

Создан скрипт `scripts/setup-encoding.ps1` для быстрой настройки кодировки:

```powershell
.\scripts\setup-encoding.ps1
```

## Проверка настроек

Проверить текущие настройки Git:

```powershell
git config --list | Select-String -Pattern "encoding|quotepath"
```

Ожидаемый вывод:
```
core.quotepath=false
i18n.commitencoding=utf-8
i18n.logoutputencoding=utf-8
gui.encoding=utf-8
```

## Исправление старых коммитов

Если в истории Git уже есть коммиты с неправильной кодировкой, их можно переписать:

### Вариант 1: Переписать последние N коммитов

```powershell
# Переписать последние 3 коммита
git rebase -i HEAD~3

# В открывшемся редакторе для каждого коммита измените:
# pick -> reword

# Git попросит переписать сообщение коммита
# После завершения:
git push --force-with-lease
```

⚠️ **ВНИМАНИЕ:** Force push изменяет историю Git. Используйте только для личных репозиториев или после согласования с командой.

### Вариант 2: Оставить как есть

Если коммиты уже запушены в публичный репозиторий, лучше оставить их как есть, чтобы не нарушать историю.

## Предотвращение проблем в будущем

### 1. Используйте UTF-8 везде

- Все файлы должны быть сохранены в UTF-8
- Редакторы кода должны быть настроены на UTF-8
- Терминал должен использовать UTF-8

### 2. Проверяйте кодировку перед коммитом

```powershell
# Просмотр изменений с правильной кодировкой
git diff

# Просмотр последних коммитов
git log --oneline -5
```

### 3. Используйте правильные инструменты

- **GitHub Desktop**: автоматически использует UTF-8
- **VS Code**: настраивается на UTF-8 по умолчанию
- **PowerShell**: требует дополнительной настройки (уже выполнено)

## Полезные команды

```powershell
# Проверить текущую кодировку консоли
chcp

# Установить UTF-8 для текущей сессии
chcp 65001

# Просмотр Git конфигурации
git config --list

# Просмотр профиля PowerShell
Get-Content $PROFILE

# Редактирование профиля PowerShell
notepad $PROFILE
```

## Ссылки

- [Git UTF-8 Configuration](https://git-scm.com/docs/git-config#Documentation/git-config.txt-i18ncommitEncoding)
- [PowerShell Encoding](https://docs.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding)
- [Windows Console Code Pages](https://docs.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences)

