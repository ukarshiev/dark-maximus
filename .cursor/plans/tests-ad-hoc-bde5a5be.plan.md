<!-- bde5a5be-df8b-48cf-ae3e-eab6015a42de 6882eb52-2aa8-4bdc-8c72-5f6b0659dfe4 -->
# План агрессивной очистки tests/ad-hoc

## Цель

Удалить все одноразовые скрипты, выполненные миграции, исторические отчёты и проверки, оставив только рабочие инструменты для управления дефектами Allure и универсальные утилиты.

## Что оставляем

### Скрипты для работы с Allure дефектами (корень tests/ad-hoc/)

- `export_allure_defects.py` - экспорт дефектов из Allure отчёта
- `analyze_allure_defects.py` - анализ дефектов и создание отчёта
- `create_github_issues.py` - создание GitHub Issues из дефектов
- `CREATE_ISSUES_INSTRUCTIONS.md` - инструкция по использованию

### Универсальные утилиты (tests/ad-hoc/utils/)

- `simulate_yookassa_webhook.py` - симуляция webhook от YooKassa (полезно для тестирования)
- `simulate_new_user.py` - симуляция нового пользователя (полезно для тестирования)
- `verify_logging_setup.py` - проверка настройки логирования
- `test_utils.py` - универсальные утилиты для работы с Unicode
- `get_credentials.py` - получение credentials из БД
- `show_transactions.py` - просмотр транзакций (полезно для отладки)
- `create_demo_transaction.py` - создание демо-транзакции (полезно для тестирования)
- `generate_test_link.py` - генерация тестовых ссылок
- `__init__.py` - для корректной работы Python пакета

### Актуальные отчёты (tests/ad-hoc/reports/)

- `allure-defects-report.md` - актуальный отчёт о дефектах (может быть перегенерирован)
- `__init__.py` - для корректной работы Python пакета

## Что удаляем

### Одноразовые тесты (tests/ad-hoc/tests/)

Удалить все файлы из `tests/ad-hoc/tests/`, кроме `__init__.py`:

- Все `test_*.py` файлы (38 файлов) - одноразовые тесты для конкретных проблем
- `test_real_install.sh` - одноразовый скрипт установки

### Проверочные скрипты (tests/ad-hoc/checks/)

Удалить все файлы из `tests/ad-hoc/checks/`, кроме `__init__.py`:

- Все `check_*.py` и `check_*.sh` файлы (15 файлов) - проверки конкретных проблем

### Выполненные миграции (tests/ad-hoc/migrations/)

Удалить все файлы из `tests/ad-hoc/migrations/`, кроме `__init__.py`:

- `migrate_add_user_columns.py`
- `migrate_database_schema.py`
- `migrate_expiry_dates_to_utc.py`
- `migrate_promo_codes_columns.py`

### Финальные проверки (tests/ad-hoc/final/)

Удалить весь каталог `tests/ad-hoc/final/`:

- `final_comparison.py`
- `final_db_comparison.py`
- `final_deeplink_test.py`
- `final_timezone_verification.py`
- `final_verification.py`
- `__init__.py`
- `__pycache__/`

### Резервные копии (tests/ad-hoc/backups/)

Удалить весь каталог `tests/ad-hoc/backups/`:

- `backup_before_timezone_migration.py`
- `__init__.py`

### Одноразовые утилиты (tests/ad-hoc/utils/)

Удалить одноразовые утилиты из `tests/ad-hoc/utils/`:

- `add_description_to_migration_history.py` - одноразовая миграция
- `add_timezone_column.py` - одноразовая миграция
- `apply_migration.py` - одноразовая утилита
- `cleanup_temp_table.py` - одноразовая очистка
- `compare_db_structure.py` - одноразовое сравнение
- `compare_json_structures.py` - одноразовое сравнение
- `create_missing_tokens_sql.py` - одноразовое создание
- `create_missing_tokens.py` - одноразовое создание
- `create_real_yookassa_payment.py` - одноразовое создание
- `create_real_yookassa_tx.py` - одноразовое создание
- `enable_timezone_feature.py` - одноразовая настройка
- `fix_docker_database.py` - одноразовое исправление
- `fix_invalid_timezones.py` - одноразовое исправление
- `fix_payment_233_manual.py` - исправление конкретного платежа
- `get_credentials.py` - оставляем (может пригодиться)
- `initialize_keys_count_for_existing_users.py` - одноразовая инициализация
- `investigate_token_issue.py` - одноразовое расследование
- `list_users_with_timezone.py` - одноразовый список
- `process_payment_233_manual.py` - обработка конкретного платежа
- `setup_test_environment.ps1` - одноразовая настройка
- `verify_yookassa_transactions.py` - одноразовая проверка
- `_io_encoding.py` - внутренний файл (можно удалить, если не используется)

### Исторические отчёты (tests/ad-hoc/reports/)

Удалить исторические отчёты из `tests/ad-hoc/reports/`:

- `allure-defects-export.json` - можно перегенерировать через export_allure_defects.py
- `KAR-30_STAGE_2_REPORT.md` - исторический отчёт
- `local_db_structure.json` - одноразовая структура БД
- `remote_current.json` - одноразовые данные
- `remote_db_structure_final.json` - одноразовая структура БД
- `remote_db_structure.json` - одноразовая структура БД
- `server_users.db` - копия БД (не должна быть в репозитории)
- `README_PAYMENT_233_CHECK.md` - отчёт о конкретном платеже
- `test_promo_deeplink_fix_REPORT.md` - отчёт о конкретном исправлении
- `test_results_cabinet_links_fix.md` - отчёт о конкретном исправлении
- `test_yookassa_docker_integration.md` - отчёт о конкретном тесте
- `TESTSKIDKI50_ANALYSIS.md` - анализ конкретного промокода
- `TIMEZONE_FIX_SUMMARY.md` - отчёт о выполненном исправлении
- `TIMEZONE_FIX_TESTING.md` - отчёт о выполненном исправлении

## Порядок выполнения

1. Удалить каталоги полностью:

- `tests/ad-hoc/final/`
- `tests/ad-hoc/backups/`

2. Удалить все файлы из каталогов:

- `tests/ad-hoc/tests/` (кроме `__init__.py`)
- `tests/ad-hoc/checks/` (кроме `__init__.py`)
- `tests/ad-hoc/migrations/` (кроме `__init__.py`)

3. Удалить одноразовые утилиты из `tests/ad-hoc/utils/`:

- Все файлы из списка выше

4. Удалить исторические отчёты из `tests/ad-hoc/reports/`:

- Все файлы из списка выше

5. Проверить, что структура каталогов корректна:

- Все `__init__.py` файлы должны остаться
- Каталоги `utils/` и `reports/` должны содержать только оставленные файлы

## Результат

После очистки в `tests/ad-hoc/` останется:

- 4 файла в корне (Allure-скрипты)
- ~8-10 универсальных утилит в `utils/`
- 1 актуальный отчёт в `reports/`
- Структурные `__init__.py` файлы

Общий объём удаляемых файлов: ~70+ файлов и 2 каталога.

### To-dos

- [ ] Удалить каталоги tests/ad-hoc/final/ и tests/ad-hoc/backups/ полностью
- [ ] Удалить все одноразовые тесты из tests/ad-hoc/tests/ (кроме __init__.py)
- [ ] Удалить все проверочные скрипты из tests/ad-hoc/checks/ (кроме __init__.py)
- [ ] Удалить все выполненные миграции из tests/ad-hoc/migrations/ (кроме __init__.py)
- [ ] Удалить одноразовые утилиты из tests/ad-hoc/utils/
- [ ] Удалить исторические отчёты и БД из tests/ad-hoc/reports/
- [ ] Проверить корректность структуры каталогов после очистки