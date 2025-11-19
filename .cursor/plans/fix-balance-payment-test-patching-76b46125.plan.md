<!-- 76b46125-c4f1-40aa-abba-cf588cdbf0d7 6990b07d-ee61-41a2-b847-cad7a904b47d -->
# План исправления теста test_balance_payment_full_flow

## Проблема

Тест использует неправильный путь для патчинга `create_or_update_key_on_host`. Согласно документации pytest и принципу "patch where it's used", нужно патчить функцию там, где она используется, а не где определена.

## Анализ

1. В `handlers.py` функция импортируется как `from shop_bot.modules import xui_api`
2. Затем используется как `xui_api.create_or_update_key_on_host()`
3. Текущий патч: `patch('shop_bot.modules.xui_api.create_or_update_key_on_host')`
4. Правильный патч: `patch('shop_bot.bot.handlers.xui_api.create_or_update_key_on_host')`

## Решение

1. Изменить путь патча в тесте с `shop_bot.modules.xui_api.create_or_update_key_on_host` на `shop_bot.bot.handlers.xui_api.create_or_update_key_on_host`
2. Проверить, что другие похожие тесты используют правильный патч
3. Запустить тест и проверить отчет Allure

## Файлы для изменения

- `tests/integration/test_payments/test_balance_flow.py` - изменить путь патча в методе `test_balance_payment_full_flow`

### To-dos

- [ ] Изменить путь патча в test_balance_payment_full_flow с 'shop_bot.modules.xui_api.create_or_update_key_on_host' на 'shop_bot.bot.handlers.xui_api.create_or_update_key_on_host'
- [ ] Запустить тест и проверить, что он проходит корректно
- [ ] Проверить отчет Allure на наличие ошибок или предупреждений
- [ ] Сравнить с другими похожими тестами и убедиться в консистентности подхода