# 📚 Сводка по документации Dark Maximus

## 🎯 Быстрый старт

### Для пользователей VPN
- **Документация:** http://localhost:3001
- **Расположение:** `docs/user-docs/`
- **Содержит:** Инструкции по настройке VPN на разных платформах

### Для администраторов
- **Документация:** http://localhost:3002
- **Расположение:** `codex.docs/`
- **Содержит:** Руководство по админ-панели, API, интеграции

### Для разработчиков
- **Документация:** `docs/README.md`
- **Расположение:** `docs/`
- **Содержит:** Техническая документация, архитектура, API

## 📁 Структура документации

```
docs/
├── user-docs/              # Пользовательская документация (localhost:3001)
│   ├── index.md
│   ├── faq.md
│   ├── payment.md
│   ├── troubleshooting.md
│   └── setup/              # Инструкции по настройке
│       ├── android.md
│       ├── ios.md
│       ├── linux.md
│       ├── macos.md
│       └── windows.md
│
├── technical/              # Техническая документация
│   ├── README.md
│   ├── tutorials/          # Обучение
│   ├── how-to-guides/      # Практические задачи
│   ├── reference/          # Справочник
│   └── explanations/       # Объяснения
│
├── setup-scripts/          # Скрипты настройки
│   └── README.md
│
├── api/                    # API документация
│   ├── README.md
│   ├── keys.md
│   ├── search-users.md
│   ├── topup-balance.md
│   ├── create-notification.md
│   ├── resend-notification.md
│   ├── promo-codes.md
│   └── transaction-details.md
│
├── integrations/           # Интеграции
│   ├── yookassa.md
│   ├── yookassa-webhook-setup.md
│   └── stars.md
│
├── admin/                  # Админская документация
│   ├── quickstart.md
│   ├── guide.md
│   ├── installation.md
│   ├── api.md
│   └── security.md
│
└── *.md                    # Основные документы
```

## 🌐 Сервисы

### 1. Пользовательская Wiki (localhost:3001)
**Назначение:** Документация для конечных пользователей VPN

**Доступ:**
- URL: http://localhost:3001
- Расположение: `docs/user-docs/`
- Технология: Nginx + Docsify

**Содержимое:**
- Инструкции по настройке VPN
- FAQ
- Решение проблем
- Информация об оплате

### 2. Codex Docs (localhost:3002)
**Назначение:** Документация для администраторов

**Доступ:**
- URL: http://localhost:3002
- Расположение: `codex.docs/`
- Технология: Codex Docs

**Содержимое:**
- Руководство по админ-панели
- API документация
- Интеграции
- Безопасность

### 3. Админ-панель (localhost:1488)
**Назначение:** Веб-интерфейс управления

**Доступ:**
- URL: http://localhost:1488
- Расположение: `src/shop_bot/webhook_server/`
- Технология: Flask

**Содержимое:**
- Управление пользователями
- Управление ключами
- Управление транзакциями
- Настройки системы

## 📖 Категории документации

### 1. Tutorials (Обучение)
Пошаговые инструкции для новичков

**Примеры:**
- Установка проекта
- Быстрый старт
- Первые шаги

**Файлы:**
- `docs/installation.md`
- `docs/admin-quickstart.md`
- `docs/user-docs/setup/*.md`

### 2. How-to guides (Практические задачи)
Решения конкретных задач

**Примеры:**
- Настройка SSL
- Интеграция платежной системы
- Настройка уведомлений

**Файлы:**
- `docs/ssl-quick-guide.md`
- `docs/integrations/yookassa-webhook-setup.md`
- `docs/notifications-setup.md`

### 3. Reference (Справочник)
Техническая справочная информация

**Примеры:**
- API документация
- Структура базы данных
- Архитектура проекта

**Файлы:**
- `docs/api/*.md`
- `docs/database.md`
- `docs/architecture-rules.md`

### 4. Explanations (Объяснения)
Концептуальная информация

**Примеры:**
- О проекте
- Технологии
- Безопасность

**Файлы:**
- `docs/project-info.md`
- `docs/tech-stack.md`
- `docs/security.md`

## 🔧 Скрипты настройки

### Основные скрипты
- `install.sh` - установка проекта
- `setup-ssl.sh` - настройка SSL
- `setup-admin-docs.sh` - настройка админской документации

### Конфигурация
- `docs-config.yaml` - конфигурация документации
- `env.example` - пример переменных окружения

## 📝 Полезные ссылки

- **[Главная страница документации](README.md)**
- **[Структура документации](DOCUMENTATION-STRUCTURE.md)**
- **[План миграции](MIGRATION-PLAN.md)**
- **[Diátaxis Framework](https://diataxis.fr/)**

## 🆘 Помощь

Если у вас возникли вопросы:

1. Проверьте **[FAQ](FAQ.md)**
2. Проверьте **[Решение проблем](user-docs/troubleshooting.md)**
3. Создайте issue на [GitHub](https://github.com/ukarshiev/dark-maximus/issues)

---

**Версия:** 1.0  
**Последнее обновление:** 2025-01-XX  
**Автор:** Dark Maximus Team

