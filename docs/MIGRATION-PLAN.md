# 📋 План миграции документации

## 🎯 Цель

Реорганизовать документацию проекта Dark Maximus согласно best practices (Diátaxis Framework) для улучшения навигации и удобства использования.

## 📊 Текущая ситуация

### Проблемы
1. ❌ Много .md файлов в корне проекта
2. ❌ Нет четкого разделения между пользовательской и технической документацией
3. ❌ Файлы для настройки документации разбросаны по корню
4. ❌ Дублирование файлов (например, инструкции в `docs/user-docs/` и `instructions/`)
5. ❌ Нет четкой структуры для технической документации

### Текущая структура
```
dark-maximus/
├── *.md (много файлов в корне)
├── docs/
│   ├── user-docs/          # Пользовательская документация (localhost:3001)
│   ├── api/
│   ├── integrations/
│   └── *.md (много файлов)
├── codex.docs/             # Codex Docs (localhost:3002)
├── instructions/           # Инструкции (дубликаты)
└── codex-page-*.txt        # Временные файлы
```

## 🎯 Целевая структура

### Новая организация
```
dark-maximus/
├── README.md               # Главная страница проекта
├── CHANGELOG.md            # История изменений
├── CONTRIBUTING.md         # Руководство для контрибьюторов
├── CONTRIBUTORS.md         # Список контрибьюторов
├── SECURITY.md             # Политика безопасности
├── LICENSE                 # Лицензия
│
├── docs/                   # Вся документация
│   ├── README.md           # Главная страница документации
│   ├── DOCUMENTATION-STRUCTURE.md  # Структура документации
│   ├── MIGRATION-PLAN.md   # Этот файл
│   │
│   ├── user-docs/          # Пользовательская документация (localhost:3001)
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
│   ├── technical/          # Техническая документация (НОВОЕ!)
│   │   ├── README.md
│   │   ├── tutorials/      # Обучение
│   │   ├── how-to-guides/  # Практические задачи
│   │   ├── reference/      # Справочник
│   │   └── explanations/   # Объяснения
│   │
│   ├── setup-scripts/      # Скрипты настройки (НОВОЕ!)
│   │   └── README.md
│   │
│   ├── api/                # API документация
│   ├── integrations/       # Интеграции
│   ├── admin/              # Админская документация
│   └── *.md                # Основные документы
│
├── codex.docs/             # Codex Docs (localhost:3002)
│   ├── docs-config.yaml
│   └── ...
│
├── scripts/                # Скрипты (НОВОЕ!)
│   ├── install.sh
│   ├── setup-ssl.sh
│   ├── setup-admin-docs.sh
│   └── setup-admin-docs.bat
│
├── config/                 # Конфигурация (НОВОЕ!)
│   ├── docs-config.yaml
│   ├── env.example
│   └── nginx-docs.conf
│
└── temp/                   # Временные файлы (НОВОЕ!)
    ├── codex-page-*.txt
    ├── codex-docs-*.json
    └── codex-docs-*.md
```

## 📝 План миграции

### Этап 1: Подготовка (✅ Выполнено)
- [x] Создать новую структуру директорий
- [x] Создать README для технической документации
- [x] Создать README для скриптов настройки
- [x] Создать DOCUMENTATION-STRUCTURE.md
- [x] Создать MIGRATION-PLAN.md

### Этап 2: Миграция файлов (⏳ В процессе)
- [ ] Переместить скрипты в `scripts/`
  - [ ] `install.sh` → `scripts/install.sh`
  - [ ] `setup-ssl.sh` → `scripts/setup-ssl.sh`
  - [ ] `setup-admin-docs.sh` → `scripts/setup-admin-docs.sh`
  - [ ] `setup-admin-docs.bat` → `scripts/setup-admin-docs.bat`
  - [ ] `test-server.ps1` → `scripts/test-server.ps1`

- [ ] Переместить конфигурацию в `config/`
  - [ ] `docs-config.yaml` → `config/docs-config.yaml`
  - [ ] `env.example` → `config/env.example`
  - [ ] `docs/nginx-docs.conf` → `config/nginx-docs.conf`

- [ ] Переместить временные файлы в `temp/`
  - [ ] `codex-page-*.txt` → `temp/codex-page-*.txt`
  - [ ] `codex-docs-*.json` → `temp/codex-docs-*.json`
  - [ ] `codex-docs-*.md` → `temp/codex-docs-*.md`
  - [ ] `import-admin-docs-to-codex.js` → `temp/import-admin-docs-to-codex.js`

- [ ] Переместить документацию настройки в `docs/setup-scripts/`
  - [ ] `HOW-TO-ADD-ADMIN-DOCS.md` → `docs/setup-scripts/HOW-TO-ADD-ADMIN-DOCS.md`
  - [ ] `SETUP-ADMIN-DOCS-README.md` → `docs/setup-scripts/SETUP-ADMIN-DOCS-README.md`
  - [ ] `CODEX-DOCS-SETUP.md` → `docs/setup-scripts/CODEX-DOCS-SETUP.md`
  - [ ] `WIKI-QUICKSTART.md` → `docs/setup-scripts/WIKI-QUICKSTART.md`

- [ ] Переместить сводки в `docs/`
  - [ ] `ADMIN-DOCS-SUMMARY.md` → `docs/ADMIN-DOCS-SUMMARY.md`
  - [ ] `AUTO-DEPLOY-DOCS-SUMMARY.md` → `docs/AUTO-DEPLOY-DOCS-SUMMARY.md`

- [ ] Удалить дубликаты
  - [ ] Удалить `instructions/` (дубликат `docs/user-docs/setup/`)

### Этап 3: Обновление ссылок (⏳ Ожидание)
- [ ] Обновить ссылки в `README.md`
- [ ] Обновить ссылки в `docs/README.md`
- [ ] Обновить ссылки в `docker-compose.yml`
- [ ] Обновить ссылки в `Dockerfile`
- [ ] Обновить ссылки в `install.sh`
- [ ] Обновить ссылки в документации

### Этап 4: Обновление документации (⏳ Ожидание)
- [ ] Обновить главный `README.md`
- [ ] Обновить `docs/README.md`
- [ ] Обновить `docs/DOCUMENTATION-STRUCTURE.md`
- [ ] Создать навигацию в технической документации
- [ ] Обновить CHANGELOG.md

### Этап 5: Тестирование (⏳ Ожидание)
- [ ] Проверить работу localhost:3001 (пользовательская Wiki)
- [ ] Проверить работу localhost:3002 (Codex Docs)
- [ ] Проверить работу localhost:1488 (админ-панель)
- [ ] Проверить все ссылки
- [ ] Проверить скрипты установки

### Этап 6: Финализация (⏳ Ожидание)
- [ ] Обновить .gitignore
- [ ] Создать PR
- [ ] Получить ревью
- [ ] Смержить изменения
- [ ] Обновить документацию для пользователей

## 🔄 Обновление ссылок

### Файлы для обновления
1. `README.md` - главная страница
2. `docs/README.md` - главная страница документации
3. `docker-compose.yml` - пути к файлам
4. `Dockerfile` - пути к файлам
5. `install.sh` - пути к файлам
6. `setup-ssl.sh` - пути к файлам
7. `setup-admin-docs.sh` - пути к файлам
8. Все файлы документации

### Шаблон замены
```bash
# Старый путь
./docs-config.yaml → ./config/docs-config.yaml
./install.sh → ./scripts/install.sh
./codex-page-*.txt → ./temp/codex-page-*.txt

# Docker volumes
./docs-config.yaml → ./config/docs-config.yaml
```

## 📊 Прогресс

### Завершено
- ✅ Создана новая структура директорий
- ✅ Созданы README файлы
- ✅ Создан DOCUMENTATION-STRUCTURE.md
- ✅ Создан MIGRATION-PLAN.md

### В процессе
- ⏳ Миграция файлов
- ⏳ Обновление ссылок
- ⏳ Обновление документации

### Ожидает
- ⏸️ Тестирование
- ⏸️ Финализация

## 🎯 Результаты

После завершения миграции:

1. ✅ Четкая структура документации
2. ✅ Разделение пользовательской и технической документации
3. ✅ Организованные скрипты и конфигурация
4. ✅ Нет дубликатов файлов
5. ✅ Улучшенная навигация
6. ✅ Соответствие best practices

## 📚 Дополнительные ресурсы

- [Diátaxis Framework](https://diataxis.fr/)
- [Write the Docs](https://www.writethedocs.org/)
- [Documentation Best Practices](https://documentation.divio.com/)

---

**Версия:** 1.0  
**Дата создания:** 2025-01-XX  
**Статус:** В процессе  
**Автор:** Dark Maximus Team

