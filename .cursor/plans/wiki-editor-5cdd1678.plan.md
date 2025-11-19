<!-- 5cdd1678-ed97-4c03-86b3-15cefd627498 9ed49902-ae37-4644-850f-77819b396542 -->
# Удаление wiki-editor из кода

## Цель

Удалить неактуальный функционал wiki-editor из веб-панели, так как редактирование документации теперь выполняется через http://localhost:50001/

## Изменения

### 1. Удаление роутов из app.py

- Удалить функцию `wiki_editor_page()` (строки 2010-2061)
- Удалить функцию `wiki_editor_edit()` (строки 2063-2127)
- Удалить функцию `wiki_create_page()` (строки 2129-2186)
- Удалить функцию `wiki_delete_page()` (строки 2188-2225)
- Файл: `src/shop_bot/webhook_server/app.py`

### 2. Удаление шаблонов

- Удалить файл `src/shop_bot/webhook_server/templates/wiki_editor.html`
- Удалить файл `src/shop_bot/webhook_server/templates/wiki_editor_edit.html`

### 3. Удаление ссылок из навигации

- Удалить ссылку на wiki-editor из полного меню (строки 113-120)
- Удалить ссылку на wiki-editor из свернутого меню (строки 220-226)
- Файл: `src/shop_bot/webhook_server/templates/base.html`

### 4. Удаление тестов

- Удалить файл `tests/unit/test_webhook_server/test_wiki.py` (весь файл содержит только тесты для wiki-editor)

### 5. Обновление документации (опционально)

- Обновить упоминания в `docs/guides/admin/admin-panel-guide.md` (удалить раздел про wiki-editor)
- Обновить упоминания в `docs/architecture/documentation-structure.md` (удалить упоминание wiki-editor/)
- Обновить упоминания в `docs/reports/linear-task-description.md` (удалить упоминания тестов)
- CHANGELOG.md оставить без изменений (история изменений)

## Проверка после удаления

- Убедиться, что веб-панель запускается без ошибок
- Проверить, что навигация работает корректно
- Убедиться, что нет битых ссылок в шаблонах

### To-dos

- [ ] Удалить 4 роута wiki-editor из app.py (wiki_editor_page, wiki_editor_edit, wiki_create_page, wiki_delete_page)
- [ ] Удалить шаблоны wiki_editor.html и wiki_editor_edit.html
- [ ] Удалить ссылки на wiki-editor из навигации в base.html (полное и свернутое меню)
- [ ] Удалить файл test_wiki.py с тестами для wiki-editor
- [ ] Обновить документацию: удалить упоминания wiki-editor из guides и reports (опционально)