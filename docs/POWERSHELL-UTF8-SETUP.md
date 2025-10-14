# Настройка UTF-8 для PowerShell и Git

**Дата создания:** 14.10.2025

## ✅ Проблема решена!

Проблема с кодировкой UTF-8 в PowerShell и Git **полностью решена** на уровне профиля PowerShell.

## Что было сделано

### 1. Создан автоматический профиль PowerShell

Профиль PowerShell (`Microsoft.PowerShell_profile.ps1`) теперь автоматически настраивает UTF-8 при каждом запуске терминала.

**Расположение профиля:**
```
C:\Users\<ваше_имя>\OneDrive\Документы\WindowsPowerShell\Microsoft.PowerShell_profile.ps1
```

### 2. Что настраивается автоматически

При каждом запуске PowerShell профиль:

1. **Устанавливает UTF-8 для консоли:**
   - `[Console]::InputEncoding` — кодировка ввода
   - `[Console]::OutputEncoding` — кодировка вывода
   - `$OutputEncoding` — кодировка для пайпов
   - `chcp 65001` — кодовая страница консоли

2. **Настраивает PowerShell на UTF-8:**
   - `$PSDefaultParameterValues['*:Encoding'] = 'utf8'` — UTF-8 по умолчанию для всех командлетов
   - `$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'` — UTF-8 для операторов `>` и `>>`

3. **Настраивает Git для работы с UTF-8:**
   - `core.quotepath = false` — не экранировать не-ASCII символы
   - `i18n.commitencoding = utf-8` — UTF-8 для коммитов
   - `i18n.logoutputencoding = utf-8` — UTF-8 для вывода команд
   - `gui.encoding = utf-8` — UTF-8 для Git GUI
   - `core.autocrlf = false` — отключить преобразование окончаний строк

4. **Настраивает переменные окружения:**
   - `LESSCHARSET = utf-8` — UTF-8 для утилиты LESS

### 3. Добавлены вспомогательные функции

#### `Test-UTF8Encoding`

Проверяет правильность настройки UTF-8 кодировки:

```powershell
Test-UTF8Encoding
```

**Вывод:**
```
Тест кодировки UTF-8...

1. Тест консоли:
   Русский текст: Привет, мир! 🚀
   Кодировка: Unicode (UTF-8)

2. Тест Git:
   ✓ Git commit encoding: utf-8
   ✓ Git log encoding: utf-8

3. Тест PowerShell:
   ✓ Default encoding: UTF-8

Тест завершён!
```

#### `gitc <сообщение>`

Создаёт Git коммит с правильной UTF-8 кодировкой:

```powershell
# Обычный коммит
gitc "Добавлена новая функция"

# Коммит с авто-добавлением всех файлов
gitc "Исправлена ошибка" -All
```

**Преимущества:**
- Гарантирует правильную кодировку сообщения коммита
- Работает с кириллицей и эмодзи
- Создаёт временный файл в UTF-8 без BOM
- Автоматически удаляет временный файл

## Как использовать

### Вариант 1: Просто откройте новый терминал

Профиль загрузится автоматически при запуске PowerShell. Вы увидите:

```
Настройка UTF-8...
  ✓ Кодировка PowerShell: UTF-8
  ✓ Кодировка по умолчанию для командлетов: UTF-8
  ✓ Настройки Git: UTF-8
  ✓ Переменные окружения: UTF-8

Текущие настройки кодировки:
  Input Encoding:  Unicode (UTF-8)
  Output Encoding: Unicode (UTF-8)
  PowerShell Output: Unicode (UTF-8)

✓ Профиль PowerShell загружен успешно!

Доступные команды:
  Test-UTF8Encoding  - Проверить настройки кодировки
  gitc <сообщение>   - Создать коммит с правильной кодировкой
```

### Вариант 2: Используйте функцию `gitc` для коммитов

Вместо обычного `git commit -m`:

```powershell
# ❌ Неправильно (может быть проблема с кодировкой)
git commit -m "Добавлена новая функция"

# ✅ Правильно (гарантированная правильная кодировка)
gitc "Добавлена новая функция"
```

### Вариант 3: Проверьте настройки

Если сомневаетесь, что всё работает правильно:

```powershell
Test-UTF8Encoding
```

## Проверка работы

### 1. Проверка кодировки PowerShell

```powershell
# Проверка кодировки консоли
[Console]::OutputEncoding.EncodingName
# Должно быть: Unicode (UTF-8)

# Проверка кодировки PowerShell
$OutputEncoding.EncodingName
# Должно быть: Unicode (UTF-8)
```

### 2. Проверка настроек Git

```powershell
# Проверка настроек Git
git config --global i18n.commitencoding
# Должно быть: utf-8

git config --global i18n.logoutputencoding
# Должно быть: utf-8
```

### 3. Тестовый коммит

```powershell
# Создайте тестовый коммит с кириллицей
gitc "Тестовый коммит с кириллицей и эмодзи 🚀"

# Проверьте, что коммит создан правильно
git log -1 --pretty=format:"%s"
# Должно отображаться: Тестовый коммит с кириллицей и эмодзи 🚀
```

## Устранение проблем

### Проблема: Профиль не загружается

**Решение:**

1. Проверьте, что профиль существует:
   ```powershell
   Test-Path $PROFILE
   # Должно быть: True
   ```

2. Проверьте политику выполнения:
   ```powershell
   Get-ExecutionPolicy
   # Должно быть: RemoteSigned или Unrestricted
   ```

3. Если политика слишком строгая, измените её:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

4. Перезагрузите профиль вручную:
   ```powershell
   . $PROFILE
   ```

### Проблема: Кракозябры в выводе

**Решение:**

1. Закройте текущий терминал и откройте новый
2. Профиль загрузится автоматически и установит правильную кодировку
3. Если проблема сохраняется, проверьте настройки терминала:
   - Windows Terminal: Settings → Profiles → Defaults → Appearance → Font
   - PowerShell ISE: Tools → Options → Fonts and Colors

### Проблема: Старые коммиты с кракозябрами

**Решение:**

Если в истории уже есть коммиты с неправильной кодировкой:

```powershell
# Просмотр истории с правильной кодировкой
$env:GIT_PAGER = "cat"
git log --pretty=format:"%h - %an, %ar : %s" --encoding=UTF-8

# Если нужно переписать историю (осторожно!)
git rebase -i HEAD~N  # где N — количество последних коммитов
```

## Дополнительная информация

### Документация

- [Проблемы с кодировкой в Git](docs/git-encoding-issues.md) — полное описание проблемы и решения
- [PowerShell Profile](https://docs.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_profiles) — официальная документация
- [Git для Windows](https://github.com/git-for-windows/git/wiki/FAQ#how-to-configure-git-to-handle-line-endings) — FAQ по кодировкам

### Полезные команды

```powershell
# Просмотр текущего профиля
notepad $PROFILE

# Перезагрузка профиля
. $PROFILE

# Проверка настройки кодировки
Test-UTF8Encoding

# Создание коммита с правильной кодировкой
gitc "Ваше сообщение коммита"
```

## Заключение

Теперь проблема с кодировкой UTF-8 в PowerShell и Git **полностью решена**. Просто откройте новый терминал PowerShell, и всё будет работать автоматически!

**Больше не нужны:**
- ❌ Ручные скрипты для настройки кодировки
- ❌ Запуск `chcp 65001` перед каждой командой
- ❌ Создание временных файлов для коммитов
- ❌ Опасения о кракозябрах в коммитах

**Всё работает автоматически!** 🎉

