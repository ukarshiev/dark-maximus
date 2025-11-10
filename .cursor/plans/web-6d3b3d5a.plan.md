<!-- 6d3b3d5a-3292-4202-9b7d-ee43db8717a4 55aa8327-b16c-4805-b4ea-f48e8926f2b1 -->
# План правок по платежам и выдаче ключей

1. Вернуть клавиатуру в сообщении «Ваш ключ готов»

- В `src/shop_bot/bot/keyboards.py` переписать `create_key_info_keyboard`: заменить `web_app` на обычные URL-кнопки, добавить явные callback-кнопки «Продлить» и «Инструкции», при наличии `subscription_link` добавлять кнопку «Открыть подписку».
- В `process_successful_payment` и `process_successful_yookassa_payment` (`src/shop_bot/bot/handlers.py`) после `add_new_key` гарантировать получение `key_id`: если функция вернула `None`, заново извлечь ключ по email и использовать его ID перед передачей в `create_key_info_keyboard`.

2. Устранить зависание транзакций YooKassa

- При создании платежей (`show_payment_options`, `topup_pay_yookassa`) писать в `metadata` поле `host_code` без эмодзи и хранить идентификатор плана/ключа.
- В `yookassa_webhook_handler` (`src/shop_bot/webhook_server/app.py`) искать хост по `host_code`; если не найден — переключать статус транзакции в `failed` и логировать подробности вместо вечного `pending`.
- В `src/shop_bot/modules/xui_api.py` вокруг `_panel_update_client_quota` и чтения JSON добавить fallback: при HTTP 200 и пустом ответе считать операцию успешной и не ломать выдачу ключа.

3. Вернуть локальное тестирование YooKassa

- В `handlers.py` добавить настройку `yookassa_local_stub`: при `test_mode` и `localhost` вместо реального платежа сразу вызывать `process_successful_payment` и помечать запись в БД как тестовую.
- Описать сценарий в `docs/guides/dev/yookassa-local.md`, дописать изменения в `CHANGELOG.md` и увеличить версию в `pyproject.toml`.

### To-dos

- [ ] Вернуть инлайн-кнопки под сообщением «Ваш ключ готов» через переработку клавиатуры и получение key_id
- [ ] Исправить зависание YooKassa-платежей за счёт host_code и корректного статуса при ошибке
- [ ] Добавить тестовый stub для YooKassa на localhost и обновить документацию