# 💻 Руководства для разработчиков

> Дата последней редакции: 24.10.2025

Инструкции по настройке окружения разработки и работе с кодом.

## Содержание

- [Настройка PowerShell UTF-8](powershell-utf8-setup.md) — Полная настройка кодировки в Windows
- [Быстрая настройка PowerShell UTF-8](powershell-utf8-quickstart.md) — Краткая инструкция
- [Рефакторинг веб-сетки](web-grid-refactor.md) — Документация по обновлению UI компонентов

## Настройка окружения

### Windows
- PowerShell 7+
- Node.js 20+
- Python 3.11+
- Git с правильной кодировкой UTF-8

### Linux/macOS
- Bash/Zsh
- Node.js 20+
- Python 3.11+

## Работа с монорепозиторием

Проект использует Nx для управления монорепозиторием:

```bash
# Запуск всех сервисов
npm run serve

# Сборка конкретного проекта
npx nx build bot

# Тесты
npm run test
```

## См. также

- [Архитектура проекта](../../architecture/project-info.md)
- [Техстек](../../reference/tech-stack.md)
- [Решение проблем с кодировкой](../../troubleshooting/encoding-issues.md)

