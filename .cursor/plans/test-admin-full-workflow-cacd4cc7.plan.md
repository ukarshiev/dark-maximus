<!-- cacd4cc7-a596-4a79-b363-d97b9b07f9a5 20588eaf-2d39-400f-99ba-5ba2d851ba6b -->
# План исправления теста test_admin_full_workflow

## Проблема

Тест `test_admin_full_workflow` падает с ошибкой:

```
AssertionError: Ожидался статус 200, получен 302
```

## Причина

Роут `/` в `src/shop_bot/webhook_server/app.py` (строки 504-507) всегда делает редирект на `/dashboard`:

```python
@flask_app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard_page'))
```

Это нормальное поведение приложения - главная страница редиректит на dashboard. Тест не следует за редиректом, поэтому получает 302 вместо 200.

## Решение

Использовать `follow_redirects=True` в запросе к `/`, чтобы следовать за редиректом и получить финальный ответ от `/dashboard` со статусом 200.

## Изменения

### Файл: `tests/integration/test_web_panel/test_admin_workflow.py`

**Строка 120:** Изменить запрос к `/` с добавлением `follow_redirects=True`:

```python
# Было:
response = authenticated_session.get('/')

# Станет:
response = authenticated_session.get('/', follow_redirects=True)
```

## Проверка

1. Запустить тест: `docker compose exec monitoring pytest tests/integration/test_web_panel/test_admin_workflow.py::TestAdminWorkflow::test_admin_full_workflow -v`
2. Проверить отчет в Allure: `http://localhost:5050/allure-docker-service/projects/default/reports/latest/index.html`
3. Убедиться, что тест проходит и все три шага (Dashboard, Users, Keys) возвращают статус 200

## Дополнительные проверки

- Убедиться, что сессия сохраняется между запросами (фикстура `authenticated_session` работает корректно)
- Проверить, что редирект идет на `/dashboard`, а не на `/login` (что означало бы проблему с сессией)

### To-dos

- [ ] Исправить тест test_admin_full_workflow: добавить follow_redirects=True к запросу GET /
- [ ] Запустить тест и проверить, что он проходит
- [ ] Проверить отчет в Allure и убедиться, что тест отображается как успешный