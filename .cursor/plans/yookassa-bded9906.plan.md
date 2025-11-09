<!-- bded9906-b207-4cd0-86fd-f1cb69367163 d28238ee-34ce-4681-9c4f-1675821be35c -->
# Полное пересоздание toggle для yookassa_test_mode

## Задача

Удалить весь существующий код toggle и пересоздать его с нуля с гарантированно работающей логикой сохранения в БД.

## Шаги выполнения

### 1. Удаление старого кода

#### HTML (settings.html):

- Удалить строки 840-860: весь блок с toggle (hidden input, label, checkbox)
- Удалить строки 928: id="yookassa_test_mode_fields" 
- Удалить строки 1817-1819: вызов toggleYooKassaMode() в DOMContentLoaded
- Удалить строки 2614-2635: функция toggleYooKassaMode() в inline script

#### JavaScript (script.js):

- Удалить строки 2740-2765: функция toggleYooKassaMode()

#### CSS (если есть специфичные стили):

- Проверить и удалить стили связанные с yookassa_test_mode toggle

### 2. Создание нового toggle с нуля

#### HTML структура:

- Создать простой checkbox без hidden input
- Использовать стандартный паттерн: `<input type="checkbox" name="yookassa_test_mode" value="true">`
- Checkbox checked = тестовый режим ON (true)
- Checkbox unchecked = тестовый режим OFF (false)

#### Серверная обработка (app.py):

- Упростить логику: `value = 'true' if request.form.get('yookassa_test_mode') == 'true' else 'false'`
- Убрать сложную логику с getlist() и hidden inputs
- Оставить детальное логирование для отладки

### 3. Проверка логики

- Проверить что checkbox отправляет правильное значение
- Проверить что сервер правильно обрабатывает значение
- Проверить что значение сохраняется в БД
- Проверить что значение читается из БД при загрузке страницы

## Файлы для изменения

- `src/shop_bot/webhook_server/templates/settings.html` - удалить старый toggle, создать новый
- `src/shop_bot/webhook_server/static/js/script.js` - удалить функцию toggleYooKassaMode()
- `src/shop_bot/webhook_server/app.py` - упростить логику обработки checkbox

### To-dos

- [ ] Добавить детальное логирование в save_payment_settings для отображения значений из формы
- [ ] Проверить и исправить логику обработки checkbox с использованием getlist()
- [ ] Проверить порядок hidden input и checkbox в HTML шаблоне
- [ ] Протестировать переключение toggle и проверить логи и БД