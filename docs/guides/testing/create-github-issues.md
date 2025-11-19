# Инструкция по созданию GitHub Issues для дефектов Allure

> **Дата последней редакции:** 27.01.2025

## Шаг 1: Получение GitHub Personal Access Token

1. Перейдите на https://github.com/settings/tokens
2. Нажмите "Generate new token" → "Generate new token (classic)"
3. Укажите название токена: `Allure Defects Issues`
4. Выберите срок действия (рекомендуется: 90 дней или "No expiration")
5. Выберите права доступа:
   - ✅ `repo` (полный доступ к репозиторию)
6. Нажмите "Generate token"
7. **ВАЖНО:** Скопируйте токен сразу (он больше не будет показан!)

## Шаг 2: Установка токена в PowerShell

```powershell
# Временная установка (только для текущей сессии)
$env:GITHUB_TOKEN='ваш-токен-здесь'

# Или постоянная установка (для текущего пользователя)
[System.Environment]::SetEnvironmentVariable('GITHUB_TOKEN', 'ваш-токен-здесь', 'User')
```

## Шаг 3: Запуск скрипта создания Issues

```powershell
# Проверка токена
if ($env:GITHUB_TOKEN) { Write-Host "✅ Токен установлен" } else { Write-Host "❌ Токен не установлен" }

# Запуск скрипта (сначала в режиме DRY RUN для проверки)
python tests/ad-hoc/create_github_issues.py --dry-run

# Если всё выглядит правильно, запустите без --dry-run
python tests/ad-hoc/create_github_issues.py
```

## Шаг 4: Проверка созданных Issues

После создания Issues проверьте:
- Все Issues созданы: https://github.com/ukarshiev/dark-maximus/issues
- Issues с меткой `allure`: https://github.com/ukarshiev/dark-maximus/issues?q=is%3Aissue+label%3Aallure

## Примечания

- Скрипт автоматически проверяет, не созданы ли Issues уже (по названию теста)
- Если Issue уже существует, он будет пропущен
- Все Issues будут иметь метку `allure` для удобной фильтрации
- Критичные дефекты получат метку `critical`

## Безопасность

⚠️ **НЕ КОММИТЬТЕ ТОКЕН В РЕПОЗИТОРИЙ!**
- Токен должен быть только в переменных окружения
- Не добавляйте токен в `.env` файл, если он коммитится в репозиторий
- Используйте GitHub Secrets для CI/CD

