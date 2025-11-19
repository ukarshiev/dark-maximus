<!-- 725d4ef1-52a6-484f-9817-2eb2ba0dbc45 01470e87-a753-4aaf-b0bf-9c19352bf8b2 -->
# Комплексное внедрение проверки линтеров в CI/CD

## Цель

Добавить автоматическую проверку качества кода через линтеры для всех языков проекта (Python, TypeScript/JavaScript, HTML, CSS, Jinja2) в GitHub Actions CI/CD pipeline, чтобы обеспечить единообразие кода на всех уровнях стека и предотвратить попадание некорректного кода в репозиторий.

## Текущее состояние

### Python (backend)

- В проекте есть команда `npx nx run bot:lint` (pylint)
- В Makefile есть команды `make check` (pylint) и `make format` (black)
- Зависимости pylint и black в `pyproject.toml` в секции `[project.optional-dependencies]dev`
- В CI/CD (`.github/workflows/ci.yml`) отсутствует проверка линтера

### TypeScript/JavaScript (codex.docs)

- ESLint уже настроен в `codex.docs/src/backend/.eslintrc` и `codex.docs/src/frontend/.eslintrc`
- Команда `yarn lint` в `codex.docs/package.json` проверяет только backend TypeScript
- Нет проверки для vanilla JavaScript файлов в `apps/user-cabinet/static/js/` и `src/shop_bot/webhook_server/static/js/`

### HTML

- Нет линтера для HTML файлов
- Файлы находятся в:
  - `src/shop_bot/webhook_server/templates/` (Jinja2 шаблоны Flask)
  - `apps/user-cabinet/templates/` (Jinja2 шаблоны)
  - `apps/web-interface/src/index.html` (обычный HTML)

### CSS

- Нет линтера для CSS файлов
- Файлы находятся в:
  - `src/shop_bot/webhook_server/static/css/`
  - `apps/user-cabinet/static/css/`

## Изменения

### 1. Обновление зависимостей

#### Python (`pyproject.toml`)

- Добавить `djlint` в секцию `[project.optional-dependencies]dev` для проверки Jinja2 шаблонов

#### Node.js (`package.json`)

- Добавить в `devDependencies`:
  - `htmlhint` - линтер для HTML
  - `stylelint` - линтер для CSS
  - `stylelint-config-standard` - стандартная конфигурация для stylelint
  - `eslint` - для vanilla JavaScript файлов (если еще не установлен глобально)

### 2. Создание конфигурационных файлов

#### HTML (`htmlhint.config.json` или `.htmlhintrc`)

- Создать конфигурацию для проверки HTML файлов
- Настроить правила для валидности HTML, доступности, производительности

#### CSS (`.stylelintrc.json`)

- Создать конфигурацию для проверки CSS файлов
- Использовать стандартный набор правил
- Настроить игнорирование файлов Tailwind (например, `tw.css`)

#### ESLint для vanilla JavaScript (`.eslintrc.json` в корне)

- Создать конфигурацию для JavaScript файлов вне codex.docs
- Настроить для vanilla JS без TypeScript

#### djlint для Jinja2 (`.djlintrc` или `pyproject.toml`)

- Создать конфигурацию для проверки Jinja2 шаблонов Flask
- Настроить профиль для Jinja2 (не Django)

### 3. Обновление `.github/workflows/ci.yml`

Создать отдельный job `lint` с несколькими шагами для разных языков:

#### Job: `lint`

- Установка Python 3.11 и Node.js (actions/setup-node)
- Установка зависимостей:
  - Python: `pip install -e ".[dev]"`
  - Node.js: `npm install` (для установки htmlhint, stylelint, eslint)
- Запуск линтеров в отдельных шагах:

  1. **Python linting:**

     - `pylint src/shop_bot/ --disable=C0111,C0103 --fail-under=7.0`
     - `black --check src/shop_bot/`

  1. **Jinja2 templates linting:**

     - `djlint --check src/shop_bot/webhook_server/templates/ apps/user-cabinet/templates/`

  1. **TypeScript/JavaScript linting:**

     - ESLint для codex.docs: `cd codex.docs && yarn lint`
     - ESLint для vanilla JS: `eslint apps/user-cabinet/static/js/ src/shop_bot/webhook_server/static/js/ apps/web-interface/server.js`

  1. **HTML linting:**

     - `htmlhint apps/web-interface/src/*.html`

  1. **CSS linting:**

     - `stylelint "src/shop_bot/webhook_server/static/css/*.css" "apps/user-cabinet/static/css/*.css" --ignore-path .gitignore`

#### Job: `test`

- Обновить зависимость: `needs: lint` (тесты запускаются только после успешной проверки линтера)

#### Job: `build`

- Оставить зависимость `needs: test` (неявно зависит от lint через test)

### 4. Обновление команд Nx и Makefile

#### `apps/bot/project.json`

- Оставить команду `lint` как есть (только pylint)

#### `Makefile`

- Обновить команду `check` для запуска всех линтеров локально:
  - Добавить шаги для htmlhint, stylelint, djlint, eslint

#### `package.json` (корень)

- Добавить скрипты:
  - `lint:html` - запуск htmlhint
  - `lint:css` - запуск stylelint
  - `lint:js` - запуск eslint для vanilla JS
  - `lint:all` - запуск всех фронтенд линтеров

### 5. Игнорирование файлов

#### `.gitignore` или `.htmlhintignore`

- Игнорировать сгенерированные файлы (например, `tw.css` из Tailwind)
- Игнорировать файлы из allure-report, node_modules

#### `.stylelintignore`

- Игнорировать сгенерированные CSS файлы (например, `tw.css`)
- Игнорировать файлы из allure-report

## Файлы для изменения/создания

1. `.github/workflows/ci.yml` - добавить job `lint` с шагами для всех линтеров
2. `pyproject.toml` - добавить `djlint` в dev зависимости
3. `package.json` - добавить htmlhint, stylelint, stylelint-config-standard в devDependencies
4. `.htmlhintrc` или `htmlhint.config.json` - создать конфигурацию для HTML
5. `.stylelintrc.json` - создать конфигурацию для CSS
6. `.eslintrc.json` (в корне) - создать конфигурацию для vanilla JavaScript
7. `.djlintrc` - создать конфигурацию для Jinja2
8. `Makefile` - обновить команду `check` для запуска всех линтеров
9. `package.json` - добавить скрипты для фронтенд линтеров

## Команды для локальной проверки

### Перед коммитом:

```powershell
# Python
npx nx run bot:lint
black --check src/shop_bot/

# Jinja2 шаблоны
djlint --check src/shop_bot/webhook_server/templates/ apps/user-cabinet/templates/

# TypeScript/JavaScript
cd codex.docs && yarn lint
eslint apps/user-cabinet/static/js/ src/shop_bot/webhook_server/static/js/

# HTML
htmlhint apps/web-interface/src/*.html

# CSS
stylelint "src/shop_bot/webhook_server/static/css/*.css" "apps/user-cabinet/static/css/*.css"

# Или через npm
npm run lint:all
```

## Преимущества комплексного подхода

- Единообразие кода на всех уровнях стека (backend, frontend, templates, styles)
- Раннее обнаружение проблем: ошибки выявляются до запуска тестов
- Экономия времени CI: тесты не запускаются, если код не соответствует стандартам
- Визуализация в GitHub: отдельный статус для проверки линтера в PR
- Соответствие best practices: все современные проекты проверяют все типы файлов

### To-dos

- [ ] Добавить зависимости: djlint в pyproject.toml (dev), htmlhint, stylelint, stylelint-config-standard, eslint в package.json (devDependencies)
- [ ] Создать конфигурационные файлы: .htmlhintrc, .stylelintrc.json, .eslintrc.json (корень), .djlintrc для настройки линтеров
- [ ] Добавить job lint в .github/workflows/ci.yml с шагами для Python (pylint + black), Jinja2 (djlint), TypeScript/JS (eslint), HTML (htmlhint), CSS (stylelint)
- [ ] Обновить job test в .github/workflows/ci.yml: добавить зависимость needs: lint
- [ ] Обновить Makefile: расширить команду check для запуска всех линтеров локально
- [ ] Добавить npm скрипты в package.json: lint:html, lint:css, lint:js, lint:all для удобного запуска фронтенд линтеров
- [ ] Протестировать все линтеры локально: убедиться что все команды работают корректно перед коммитом
- [ ] Проверить работу CI/CD: сделать тестовый push/PR и убедиться что job lint работает корректно и блокирует сборку при ошибках