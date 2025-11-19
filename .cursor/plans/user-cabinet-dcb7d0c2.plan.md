<!-- dcb7d0c2-c69d-4dc3-90ec-9fcf7692da67 7710e2cb-3fab-4833-be30-ed34b9ca6321 -->
# План: Исправление пропуска тестов user-cabinet

## Проблема

Все тесты класса `TestUserCabinet` (13 тестов) пропускаются (skipped) в Allure отчете, потому что фикстура `flask_app` не может найти файл приложения `apps/user-cabinet/app.py` в Docker контейнере `monitoring`.

### Текущая ситуация

- В `docker-compose.yml` volume смонтирован как: `./apps:/app/apps`
- Фикстура проверяет пути:

  1. `project_root / "apps" / "user-cabinet" / "app.py"` (где project_root вычисляется как `Path(__file__).parent.parent.parent.parent`)
  2. `Path("/app/project/apps/user-cabinet/app.py")` - **НЕПРАВИЛЬНЫЙ ПУТЬ** (нет `/app/project`)
  3. `Path("/app/apps/user-cabinet/app.py")` - правильный путь для Docker

### Корневые причины

1. В списке `possible_paths` указан неверный путь `/app/project/apps/user-cabinet/app.py`, которого не существует
2. Отсутствует отладочная информация о том, какие пути проверялись и почему они не найдены
3. Возможно, `project_root` вычисляется неправильно в контейнере

## Решение

### 1. Исправить список путей в фикстуре `flask_app`

**Файл:** `tests/unit/test_user_cabinet/test_cabinet.py`

- Удалить неправильный путь `/app/project/apps/user-cabinet/app.py`
- Добавить правильные пути для Docker окружения:
  - `/app/apps/user-cabinet/app.py` (основной Docker путь)
  - `project_root / "apps" / "user-cabinet" / "app.py"` (локальная разработка и альтернативный путь)

### 2. Улучшить логирование для диагностики

**Файл:** `tests/unit/test_user_cabinet/test_cabinet.py`

- Добавить логирование проверяемых путей перед проверкой
- Добавить информацию о текущем `project_root` в сообщение об ошибке
- Использовать `allure.attach` для сохранения отладочной информации в Allure отчет

### 3. Добавить альтернативный способ определения пути

**Файл:** `tests/unit/test_user_cabinet/test_cabinet.py`

- Проверить наличие переменной окружения `PROJECT_ROOT`
- Использовать абсолютный путь от корня проекта, если доступен
- Добавить проверку через `os.getcwd()` как fallback

## Детали реализации

### Исправление фикстуры flask_app

```python
@pytest.fixture
def flask_app(self):
    """Фикстура для Flask приложения"""
    import sys
    import importlib.util
    import os
    from pathlib import Path
    
    # Определяем project_root разными способами
    test_file = Path(__file__).resolve()
    project_root_from_test = test_file.parent.parent.parent.parent
    
    # Проверяем переменную окружения
    project_root_env = os.getenv('PROJECT_ROOT')
    if project_root_env:
        project_root_env = Path(project_root_env).resolve()
    
    # Проверяем текущую рабочую директорию
    cwd = Path(os.getcwd()).resolve()
    
    # Формируем список возможных путей
    possible_paths = []
    
    # Локальная разработка (от файла теста)
    possible_paths.append(project_root_from_test / "apps" / "user-cabinet" / "app.py")
    
    # Docker окружение (основной путь)
    possible_paths.append(Path("/app/apps/user-cabinet/app.py"))
    
    # Если есть переменная окружения
    if project_root_env:
        possible_paths.append(project_root_env / "apps" / "user-cabinet" / "app.py")
    
    # От текущей рабочей директории
    possible_paths.append(cwd / "apps" / "user-cabinet" / "app.py")
    
    # Убираем дубликаты, сохраняя порядок
    seen = set()
    unique_paths = []
    for path in possible_paths:
        path_str = str(path)
        if path_str not in seen:
            seen.add(path_str)
            unique_paths.append(path)
    
    # Логируем проверяемые пути для отладки
    paths_info = "\n".join([f"  - {p} (exists: {p.exists()})" for p in unique_paths])
    logging.info(f"Checking paths for user-cabinet app.py:\n{paths_info}")
    
    app_file = None
    for path in unique_paths:
        if path.exists():
            app_file = path
            logging.info(f"Found app.py at: {app_file}")
            break
    
    # Если файл не найден, пропускаем тест с детальной информацией
    if not app_file:
        error_msg = f"App file not found in any of the expected locations:\n{paths_info}\nProject root (from test): {project_root_from_test}\nCWD: {cwd}"
        logging.error(error_msg)
        pytest.skip(error_msg)
    
    # Загружаем модуль
    spec = importlib.util.spec_from_file_location("user_cabinet_app", app_file)
    app_module = importlib.util.module_from_spec(spec)
    
    # Добавляем пути для импорта
    app_dir = app_file.parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))
    if str(project_root_from_test / "src") not in sys.path:
        sys.path.insert(0, str(project_root_from_test / "src"))
    
    spec.loader.exec_module(app_module)
    flask_app = app_module.app
    
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'
    return flask_app.test_client()
```

## Файлы для изменения

- `tests/unit/test_user_cabinet/test_cabinet.py` - исправление фикстуры `flask_app`

## Ожидаемый результат

- Все тесты `TestUserCabinet` будут выполняться, а не пропускаться
- В Allure отчете будет видна причина пропуска, если файл все еще не найден
- Логирование поможет диагностировать проблемы с путями в будущем

### To-dos

- [ ] Исправить фикстуру flask_app: убрать неправильный путь /app/project/apps, добавить правильные пути и улучшить логирование
- [ ] Добавить детальное логирование проверяемых путей и причин пропуска тестов для диагностики
- [ ] Проверить, что тесты больше не пропускаются: запустить тесты в Docker контейнере и проверить Allure отчет