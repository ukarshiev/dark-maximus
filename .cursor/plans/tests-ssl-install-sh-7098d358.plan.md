<!-- 7098d358-3687-4cf6-aa70-096acdafa18d 2600d710-66bd-44b1-9826-bc515bbaa2ae -->
# План: Реализация автотестов для проверки доменов

## Цель

Создать комплекс автотестов, которые:

1. Проверяют отсутствие жестко прописанных доменов в коде
2. Проверяют корректную работу функциональности использования настроек доменов из БД
3. Предотвращают регрессии при изменении кода

## Структура тестов

### 1. Тесты на отсутствие жестко прописанных доменов

**Файл:** `tests/unit/test_security/test_hardcoded_domains.py`

**Класс:** `TestHardcodedDomains`

**Тесты:**

- `test_no_hardcoded_domains_in_python_code` - проверка отсутствия `dark-maximus.com` в Python коде (кроме документации)
- `test_no_hardcoded_subdomains_in_python_code` - проверка отсутствия паттернов `panel.dark-maximus`, `help.dark-maximus`, `docs.dark-maximus`, `app.dark-maximus` в Python коде
- `test_nginx_template_uses_variables` - проверка использования переменных `${DOMAIN}` в nginx шаблоне вместо жестких значений
- `test_scripts_use_domain_variables` - проверка использования переменных в скриптах установки (install.sh, ssl-install.sh)

**Реализация:**

- Использовать `grep` или `Path.rglob()` для поиска файлов
- Исключить из проверки: `docs/`, `CHANGELOG.md`, `*.md` файлы
- Проверять только: `src/**/*.py`, `deploy/**/*.tpl`, `*.sh`
- Использовать регулярные выражения для поиска паттернов

### 2. Тесты функциональности работы с доменами

**Файл:** `tests/unit/test_database/test_domain_settings.py`

**Класс:** `TestDomainSettings`

**Тесты:**

- `test_get_global_domain_from_db` - проверка чтения `global_domain` из БД
- `test_get_global_domain_fallback_to_domain` - проверка fallback на `domain` если `global_domain` отсутствует
- `test_get_global_domain_fallback_to_localhost` - проверка fallback на localhost если оба отсутствуют
- `test_get_user_cabinet_domain_from_db` - проверка чтения `user_cabinet_domain` из БД
- `test_get_user_cabinet_domain_returns_none` - проверка возврата None если настройка отсутствует
- `test_get_codex_docs_domain_from_db` - проверка чтения `codex_docs_domain` из БД
- `test_get_docs_domain_from_db` - проверка чтения `docs_domain` из БД

**Реализация:**

- Использовать фикстуру `temp_db` из conftest.py
- Использовать `update_setting()` для установки значений в БД
- Проверять нормализацию доменов (протокол, слэши)

### 3. Тесты нормализации доменов

**Файл:** `tests/unit/test_utils/test_domain_normalization.py`

**Класс:** `TestDomainNormalization`

**Тесты:**

- `test_add_https_protocol_if_missing` - проверка добавления `https://` если протокол отсутствует
- `test_remove_trailing_slash` - проверка удаления trailing slash
- `test_handle_domain_with_port` - проверка обработки домена с портом
- `test_handle_domain_with_path` - проверка обработки домена с путем
- `test_handle_none_and_empty_string` - проверка обработки None и пустых строк
- `test_extract_domain_from_url` - проверка извлечения домена из полного URL

**Реализация:**

- Тестировать функции нормализации из `config.py` и `database.py`
- Использовать параметризованные тесты для разных вариантов входных данных

### 4. Тесты для keyboards.py

**Файл:** `tests/unit/test_bot/test_keyboard_domains.py`

**Класс:** `TestKeyboardDomains`

**Тесты:**

- `test_setup_button_uses_codex_docs_domain` - проверка использования `codex_docs_domain` для кнопки "Настройка"
- `test_setup_button_fallback_to_default` - проверка fallback на дефолтный URL если настройка отсутствует
- `test_setup_button_url_normalization` - проверка нормализации URL (протокол, слэши)
- `test_setup_button_url_with_setup_path` - проверка добавления `/setup` к домену

**Реализация:**

- Использовать моки для `get_setting()`
- Проверять формирование `WebAppInfo` с правильным URL
- Использовать фикстуру `temp_db` для установки настроек

### 5. Тесты для database.py (TON manifest)

**Файл:** `tests/unit/test_database/test_ton_manifest_domains.py`

**Класс:** `TestTonManifestDomains`

**Тесты:**

- `test_ton_manifest_uses_global_domain_from_db` - проверка использования `global_domain` для TON manifest при инициализации БД
- `test_ton_manifest_fallback_to_domain` - проверка fallback на `domain` если `global_domain` отсутствует
- `test_ton_manifest_fallback_to_default` - проверка fallback на дефолтное значение если оба отсутствуют
- `test_ton_manifest_urls_formation` - проверка корректного формирования всех URL (manifest, icon, terms, privacy)
- `test_ton_manifest_domain_normalization` - проверка нормализации домена (протокол, слэши)

**Реализация:**

- Использовать фикстуру `temp_db`
- Устанавливать настройки через `update_setting()` перед инициализацией
- Проверять значения в `default_settings` после инициализации

### 6. Тесты для xui_api.py

**Файл:** `tests/unit/test_modules/test_xui_api_domains.py`

**Класс:** `TestXuiApiDomains`

**Тесты:**

- `test_user_agent_uses_global_domain` - проверка использования `global_domain` в User-Agent
- `test_user_agent_domain_normalization` - проверка нормализации домена (удаление протокола)
- `test_user_agent_fallback_to_default` - проверка fallback на дефолтное значение
- `test_user_agent_format` - проверка формата User-Agent строки

**Реализация:**

- Использовать моки для `get_global_domain()`
- Проверять заголовки в `requests.Session`
- Использовать фикстуру `temp_db` для установки настроек

### 7. Интеграционные тесты использования доменов

**Файл:** `tests/integration/test_domain_integration.py`

**Класс:** `TestDomainIntegration`

**Тесты:**

- `test_setup_button_integration` - интеграционный тест формирования кнопки "Настройка" с правильным URL
- `test_ton_manifest_integration` - интеграционный тест формирования TON manifest с правильным доменом
- `test_user_agent_integration` - интеграционный тест формирования User-Agent с правильным доменом
- `test_all_domain_settings_together` - проверка работы всех 4 настроек доменов вместе
- `test_domain_settings_fallback_chain` - проверка цепочки fallback значений

**Реализация:**

- Использовать фикстуру `temp_db` и `mock_bot`
- Устанавливать все настройки доменов в БД
- Проверять работу всей цепочки от БД до формирования URL

### 8. Тесты для ssl-install.sh (скрипт валидации)

**Файл:** `tests/scripts/test_domain_extraction.py`

**Класс:** `TestDomainExtraction`

**Тесты:**

- `test_extract_domain_from_url_with_https` - проверка извлечения домена из URL с https://
- `test_extract_domain_from_url_with_http` - проверка извлечения домена из URL с http://
- `test_extract_domain_from_url_with_path` - проверка извлечения домена из URL с путем
- `test_extract_domain_from_url_with_port` - проверка извлечения домена из URL с портом
- `test_read_setting_from_db` - проверка чтения настройки из БД (через Python скрипт)
- `test_domain_generation_with_db_settings` - проверка генерации доменов с использованием настроек из БД

**Реализация:**

- Использовать Python для тестирования функций bash (через subprocess или прямую реализацию логики)
- Создать временную БД для тестирования `read_setting_from_db`
- Тестировать функцию `extract_domain_from_url` напрямую

## Приоритеты реализации

**Фаза 1 (Критичные - сделать в первую очередь):**

1. Тесты на отсутствие жестко прописанных доменов
2. Тесты функциональности работы с доменами
3. Тесты нормализации доменов

**Фаза 2 (Важные - сделать во вторую очередь):**

4. Тесты для keyboards.py
5. Тесты для database.py (TON manifest)
6. Интеграционные тесты использования доменов

**Фаза 3 (Опциональные - можно сделать позже):**

7. Тесты для xui_api.py
8. Тесты для ssl-install.sh (скрипт валидации)

## Технические детали

### Структура файлов

- Все тесты следуют существующей структуре проекта
- Используют фикстуры из `conftest.py` (temp_db, mock_bot)
- Следуют правилам Allure аннотаций (@allure.epic, @allure.feature, @allure.title, @allure.description)
- Используют маркеры pytest (@pytest.mark.unit, @pytest.mark.integration, @pytest.mark.database)

### Исключения для проверки жестко прописанных доменов

- `docs/` - документация
- `CHANGELOG.md` - исторические записи
- `*.md` файлы - документация
- `tests/` - тесты (могут содержать примеры)
- `nginx/nginx.conf` и `nginx/nginx-ssl.conf` - старые файлы, не используются

### Файлы для проверки

- `src/**/*.py` - весь Python код
- `deploy/**/*.tpl` - шаблоны nginx
- `*.sh` - скрипты установки (install.sh, ssl-install.sh, install-autotest.sh)

## Ожидаемый результат

После реализации всех тестов:

- Автоматическая проверка отсутствия жестко прописанных доменов при каждом запуске тестов
- Покрытие тестами всей функциональности работы с доменами
- Предотвращение регрессий при изменении кода
- Документация работы с доменами через тесты

### To-dos

- [ ] Создать tests/unit/test_security/test_hardcoded_domains.py с тестами на отсутствие жестко прописанных доменов в Python коде, nginx шаблонах и скриптах
- [ ] Создать tests/unit/test_database/test_domain_settings.py с тестами функциональности работы с доменами (get_global_domain, get_user_cabinet_domain, get_setting для всех доменов)
- [ ] Создать tests/unit/test_utils/test_domain_normalization.py с тестами нормализации доменов (протокол, слэши, порт, путь)
- [ ] Создать tests/unit/test_bot/test_keyboard_domains.py с тестами формирования кнопки Настройка с использованием codex_docs_domain
- [ ] Создать tests/unit/test_database/test_ton_manifest_domains.py с тестами формирования TON manifest URL из global_domain
- [ ] Создать tests/unit/test_modules/test_xui_api_domains.py с тестами формирования User-Agent с использованием global_domain
- [ ] Создать tests/integration/test_domain_integration.py с интеграционными тестами работы всех настроек доменов вместе
- [ ] Создать tests/scripts/test_domain_extraction.py с тестами функций извлечения домена из URL и чтения настроек из БД для ssl-install.sh