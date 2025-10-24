# 📚 Структура документации Dark Maximus

## 🎯 Обзор

Документация проекта Dark Maximus организована согласно [Diátaxis Framework](https://diataxis.fr/) для максимальной ясности и удобства использования.

## 📁 Структура директорий

```
dark-maximus/
├── README.md                          # Главная страница проекта
├── CHANGELOG.md                       # История изменений
├── CONTRIBUTING.md                    # Руководство для контрибьюторов
├── CONTRIBUTORS.md                    # Список контрибьюторов
├── SECURITY.md                        # Политика безопасности
├── LICENSE                            # Лицензия
│
├── docs/                              # Вся документация
│   ├── README.md                      # Главная страница документации
│   │
│   ├── user-docs/                     # Документация для пользователей (localhost:3001)
│   │   ├── index.md                   # Главная страница
│   │   ├── faq.md                     # FAQ
│   │   ├── payment.md                 # Оплата
│   │   ├── troubleshooting.md         # Решение проблем
│   │   └── setup/                     # Инструкции по настройке
│   │       ├── android.md
│   │       ├── ios.md
│   │       ├── linux.md
│   │       ├── macos.md
│   │       └── windows.md
│   │
│   ├── technical/                     # Техническая документация
│   │   ├── README.md                  # Главная страница
│   │   ├── tutorials/                 # Обучение (Tutorials)
│   │   ├── how-to-guides/             # Практические задачи (How-to)
│   │   ├── reference/                 # Справочник (Reference)
│   │   └── explanations/              # Объяснения (Explanations)
│   │
│   ├── setup-scripts/                 # Скрипты настройки
│   │   └── README.md                  # Описание скриптов
│   │
│   ├── api/                           # API документация
│   │   ├── README.md
│   │   ├── keys.md
│   │   ├── search-users.md
│   │   ├── topup-balance.md
│   │   ├── create-notification.md
│   │   ├── resend-notification.md
│   │   ├── promo-codes.md
│   │   └── transaction-details.md
│   │
│   ├── integrations/                  # Интеграции
│   │   ├── yookassa.md
│   │   ├── yookassa-webhook-setup.md
│   │   └── stars.md
│   │
│   ├── admin/                         # Админская документация
│   │   ├── quickstart.md
│   │   ├── guide.md
│   │   ├── installation.md
│   │   ├── api.md
│   │   └── security.md
│   │
│   ├── user-docs/                     # Пользовательская документация
│   │   ├── index.md
│   │   ├── faq.md
│   │   ├── payment.md
│   │   ├── troubleshooting.md
│   │   └── setup/
│   │       ├── android.md
│   │       ├── ios.md
│   │       ├── linux.md
│   │       ├── macos.md
│   │       └── windows.md
│   │
│   ├── wiki-editor/                   # Редактор Wiki
│   │
│   ├── architecture-rules.md          # Правила архитектуры
│   ├── database.md                    # База данных
│   ├── modules.md                     # Модули
│   ├── security.md                    # Безопасность
│   ├── tech-stack.md                  # Технологии
│   ├── project-info.md                # О проекте
│   ├── roadmap-main.md                # План модернизации (основной)
│   ├── roadmap.md                     # План развития (текущий)
│   ├── FAQ.md                         # FAQ
│   ├── features.md                    # Функции
│   ├── features-subscriptions.md      # Подписки
│   ├── referral-program.md            # Реферальная программа
│   ├── notifications-setup.md         # Уведомления
│   ├── video-instructions.md          # Видеоинструкции
│   ├── installation.md                # Установка
│   ├── server-deployment.md           # Развертывание
│   ├── production-checklist.md        # Чек-лист продакшена
│   ├── ssl-quick-guide.md             # Быстрая настройка SSL
│   ├── ssl-setup-guide.md             # Подробная настройка SSL
│   ├── wiki-deployment.md             # Развертывание Wiki
│   ├── admin-quickstart.md            # Быстрый старт админа
│   ├── admin-panel-guide.md           # Руководство по админ-панели
│   ├── dialog-api.md                  # Dialog API
│   ├── generic-cqrs-typing.md         # CQRS типизация
│   ├── test-cases-plan-unavailable.md # План тестов
│   └── nginx/                        # Конфигурация Nginx
│       └── docs.conf                 # Конфигурация для Wiki
│   ├── DOCUMENTATION-STRUCTURE.md     # Этот файл
│   │
│   └── ADMIN-DOCS-SUMMARY.md          # Сводка админской документации
│
├── codex.docs/                        # Codex Docs (localhost:3002)
│   ├── docs-config.yaml               # Конфигурация
│   └── ...
│
├── instructions/                      # Инструкции (дубликаты для бота)
│   ├── android.md
│   ├── ios.md
│   ├── linux.md
│   ├── macos.md
│   ├── windows.md
│   └── telegram-forum-setup.md
│
├── install.sh                         # Скрипт установки
├── setup-ssl.sh                       # Скрипт настройки SSL
├── setup-admin-docs.sh                # Скрипт настройки админской документации
├── setup-admin-docs.bat               # Windows версия
├── test-server.ps1                    # Тестовый сервер
├── docs-config.yaml                   # Конфигурация документации
├── env.example                        # Пример переменных окружения
│
├── ADMIN-DOCS-SUMMARY.md              # Сводка админской документации (корень)
├── AUTO-DEPLOY-DOCS-SUMMARY.md        # Сводка авто-деплоя
├── CODEX-DOCS-SETUP.md                # Настройка Codex Docs
├── HOW-TO-ADD-ADMIN-DOCS.md           # Как добавить админскую документацию
├── SETUP-ADMIN-DOCS-README.md         # Настройка админской документации
├── WIKI-QUICKSTART.md                 # Быстрый старт с Wiki
│
├── codex-page-*.txt                   # Страницы для Codex Docs (временные)
├── codex-docs-*.json                  # Данные для Codex Docs
├── codex-docs-*.md                    # Документация Codex Docs
│
└── import-admin-docs-to-codex.js      # Скрипт импорта документации
```

## 🎯 Категории документации (Diátaxis)

### 1. Tutorials (Обучение)
**Цель:** Обучить пользователя основам работы с проектом

**Примеры:**
- Установка проекта
- Быстрый старт
- Первые шаги

**Файлы:**
- `docs/installation.md`
- `docs/admin-quickstart.md`
- `docs/user-docs/setup/*.md`

### 2. How-to guides (Практические задачи)
**Цель:** Решить конкретную задачу

**Примеры:**
- Настройка SSL
- Интеграция платежной системы
- Настройка уведомлений

**Файлы:**
- `docs/ssl-quick-guide.md`
- `docs/integrations/yookassa-webhook-setup.md`
- `docs/notifications-setup.md`
- `docs/server-deployment.md`

### 3. Reference (Справочник)
**Цель:** Описать техническую информацию

**Примеры:**
- API документация
- Структура базы данных
- Архитектура проекта

**Файлы:**
- `docs/api/*.md`
- `docs/database.md`
- `docs/architecture-rules.md`
- `docs/modules.md`

### 4. Explanations (Объяснения)
**Цель:** Объяснить концепции и решения

**Примеры:**
- О проекте
- Технологии
- Безопасность

**Файлы:**
- `docs/project-info.md`
- `docs/tech-stack.md`
- `docs/security.md`
- `docs/internal/roadmap-main.md`

## 🌐 Сервисы документации

### 1. localhost:3001 - Пользовательская Wiki
**Назначение:** Документация для конечных пользователей VPN

**Содержимое:**
- `docs/user-docs/`

**Используется:** Nginx + Docsify

### 2. localhost:3002 - Codex Docs (Админская документация)
**Назначение:** Документация для администраторов

**Содержимое:**
- `codex.docs/`
- `docs/admin/`

**Используется:** Codex Docs

### 3. localhost:1488 - Админ-панель
**Назначение:** Веб-интерфейс управления

**Содержимое:**
- `src/shop_bot/webhook_server/`

**Используется:** Flask

## 📝 Рекомендации по написанию документации

### 1. Tutorials
- Пишите пошаговые инструкции
- Используйте простой язык
- Добавляйте скриншоты и примеры
- Проверяйте каждую команду

### 2. How-to guides
- Фокусируйтесь на конкретной задаче
- Используйте четкие заголовки
- Добавляйте примеры кода
- Указывайте возможные проблемы

### 3. Reference
- Используйте таблицы и списки
- Добавляйте примеры API
- Документируйте все параметры
- Обновляйте при изменениях

### 4. Explanations
- Объясняйте "почему", а не "как"
- Используйте диаграммы
- Ссылайтесь на другие документы
- Обновляйте при изменениях архитектуры

## 🔄 Процесс обновления документации

1. **Определите категорию** документа (Tutorial, How-to, Reference, Explanation)
2. **Выберите правильное место** для документа
3. **Следуйте шаблону** для категории
4. **Обновите индекс** документации
5. **Проверьте ссылки** на другие документы
6. **Обновите CHANGELOG.md**

## 📚 Дополнительные ресурсы

- [Diátaxis Framework](https://diataxis.fr/)
- [Write the Docs](https://www.writethedocs.org/)
- [Documentation Best Practices](https://documentation.divio.com/)

---

**Версия:** 2.0  
**Последнее обновление:** 2025-01-XX  
**Автор:** Dark Maximus Team

