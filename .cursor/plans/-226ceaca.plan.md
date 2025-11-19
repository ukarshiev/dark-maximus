<!-- 226ceaca-3b17-4b09-ac85-f0491b26296d 39408444-5bf0-4ed7-97ce-30d12f51f5c5 -->
# План: Преобразование теста шаблонов сообщений в полноценный unit-тест

## Цель

Преобразовать одноразовый тест `tests/ad-hoc/test_message_templates.py` в полноценный unit-тест с использованием pytest, фикстур, Allure и best practices. Создать документацию для админ-панели.

## Задачи

### 1. Обновление фикстуры temp_db

- **Файл:** `tests/conftest.py`
- **Действие:** Добавить создание таблицы `message_templates` в фикстуру `temp_db`
- **Детали:** Таблица должна содержать все необходимые поля (template_key, category, provision_mode, template_text, description, is_active, variables) и индексы

### 2. Создание нового unit-теста

- **Файл:** `tests/unit/test_utils/test_message_templates.py`
- **Действие:** Создать полноценный unit-тест с использованием pytest, фикстур и Allure
- **Структура:**
  - Класс `TestFormatTariffInfo` - тесты для `format_tariff_info()`
  - Класс `TestGetPurchaseSuccessText` - тесты для `get_purchase_success_text()` с проверкой всех режимов предоставления (key, subscription, both, cabinet, cabinet_subscription)
  - Класс `TestGetKeyInfoText` - тесты для `get_key_info_text()`
  - Класс `TestMessageTemplatesIntegration` - тесты интеграции со справочником "Тексты бота"
- **Best practices:**
  - Использовать `@pytest.mark.unit`, `@pytest.mark.database`
  - Параметризация через `@pytest.mark.parametrize` для тестирования всех режимов
  - Использовать фикстуру `temp_db` для изоляции тестов
  - Моки для внешних зависимостей (get_message_template, get_or_create_permanent_token)
  - Подробные описания в Allure: `@allure.title`, `@allure.description`, `@allure.step`, `allure.attach`

### 3. Использование Allure для детального описания

- **Элементы:**
  - `@allure.title` - краткое описание теста
  - `@allure.description` - подробное описание с HTML-разметкой
  - `@allure.severity` - уровень критичности (CRITICAL, NORMAL, MINOR)
  - `@allure.tag` - теги для фильтрации
  - `@allure.step` - шаги выполнения теста
  - `allure.attach` - прикрепление данных (входные параметры, результаты, сообщения об ошибках)

### 4. Проверка интеграции со справочником "Тексты бота"

- **Тесты:**
  - Проверка получения шаблона из БД для каждого режима предоставления
  - Проверка fallback на код при отсутствии шаблона в БД
  - Проверка подстановки переменных в шаблон
  - Проверка валидации HTML-тегов
  - Проверка корректности отображения сообщений в зависимости от режима тарифа

### 5. Создание документации для админ-панели

- **Файл:** `docs/guides/admin/message-templates-testing.md` (или аналогичный)
- **Содержимое:**
  - Описание теста и его назначение
  - Структура теста и используемые компоненты
  - Инструкции по запуску теста
  - Примеры использования
  - Описание проверяемых сценариев

### 6. Удаление старого одноразового теста

- **Файл:** `tests/ad-hoc/test_message_templates.py`
- **Действие:** Удалить после создания нового теста (или оставить как резерв)

## Технические детали

### Параметризация тестов

- Использовать `@pytest.mark.parametrize` для тестирования всех режимов предоставления:
  - `key`, `subscription`, `both`, `cabinet`, `cabinet_subscription`
- Тестировать различные комбинации входных параметров (с/без connection_string, subscription_link, cabinet_url)

### Моки

- Мок для `get_message_template()` - проверка получения шаблона из БД
- Мок для `get_or_create_permanent_token()` - проверка генерации токена для личного кабинета
- Мок для `get_user_cabinet_domain()` - проверка получения домена личного кабинета

### Фикстуры

- Использовать существующую фикстуру `temp_db` с добавлением таблицы `message_templates`
- Создать фикстуру для заполнения тестовых данных шаблонов

## Структура файлов

```
tests/unit/test_utils/
├── __init__.py
└── test_message_templates.py  # Новый файл

tests/conftest.py  # Обновление фикстуры temp_db

docs/guides/admin/
└── message-templates-testing.md  # Новая документация
```

## Ожидаемый результат

- Полноценный unit-тест с покрытием всех режимов предоставления тарифа
- Детальное описание в Allure с шагами выполнения и прикрепленными данными
- Документация для админ-панели с описанием теста и инструкциями
- Соответствие best practices pytest и Allure

### To-dos

- [ ] Обновить фикстуру temp_db в tests/conftest.py: добавить создание таблицы message_templates с полями и индексами
- [ ] Создать tests/unit/test_utils/test_message_templates.py с классами тестов для format_tariff_info, get_purchase_success_text, get_key_info_text и интеграции со справочником
- [ ] Добавить Allure аннотации (@allure.title, @allure.description, @allure.step, allure.attach) для детального описания тестов
- [ ] Добавить параметризацию тестов через @pytest.mark.parametrize для всех режимов предоставления (key, subscription, both, cabinet, cabinet_subscription)
- [ ] Добавить моки для внешних зависимостей (get_message_template, get_or_create_permanent_token, get_user_cabinet_domain)
- [ ] Создать документацию docs/guides/admin/message-templates-testing.md с описанием теста и инструкциями